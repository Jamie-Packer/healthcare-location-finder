"""Export, package and check one reference bundle.

The zip is swapped into place only after its manifest, checksums and references
agree. A failed staging directory does not replace the last accepted zip.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import duckdb

from ingest.compare import write_comparison
from ingest.contract import (
    BUNDLE_FILES,
    BUNDLE_SHA,
    BUNDLE_ZIP,
    PARQUET_TABLES,
    REFERENCE_TABLES,
    SCHEMA_VERSION,
    TABLES,
    Column,
    Table,
    attribution_markdown,
    contract_sha256,
    coverage_markdown,
    dictionary_markdown,
    supported_schema,
)
from ingest.validate import ValidationError

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "data" / "build"
STAGING = BUILD / "bundle-staging"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def _csv_relation(path: Path) -> str:
    return f"""
        read_csv(
            '{path.as_posix()}',
            header = true,
            all_varchar = true,
            quote = '"',
            escape = '"',
            delim = ',',
            strict_mode = false,
            null_padding = true,
            parallel = false,
            max_line_size = 1048576
        )
    """


def _reject_empty_text(connection: duckdb.DuckDBPyConnection, table: Table, parquet: Path) -> None:
    checks = [
        f"count(*) filter (where {_quote(column.name)} = '')"
        for column in table.columns
        if column.logical_type == "text"
    ]
    if not checks:
        return
    found = connection.execute(
        f"select {', '.join(checks)} from read_parquet('{parquet.as_posix()}')"
    ).fetchone()
    failures = [
        f"{table.filename} column {column.name} contains an empty string"
        for column, count in zip(
            (column for column in table.columns if column.logical_type == "text"),
            found or (),
        )
        if count
    ]
    if failures:
        raise ValidationError(failures)


def _export_csv(connection: duckdb.DuckDBPyConnection, table: Table, parquet: Path, dest: Path) -> None:
    if not parquet.exists():
        raise ValidationError([f"{parquet.name} is missing"])
    _reject_empty_text(connection, table, parquet)
    columns = ", ".join(_quote(column.name) for column in table.columns)
    order = ", ".join(_quote(key) for key in table.keys)
    connection.execute(
        f"""
        copy (
            select {columns}
            from read_parquet('{parquet.as_posix()}')
            order by {order}
        ) to '{dest.as_posix()}' (
            format csv,
            header true,
            quote '"',
            escape '"',
            null '',
            delim ','
        )
        """
    )


def git_commit() -> str | None:
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def worktree_dirty() -> bool:
    """True when HEAD does not contain the files this build imported."""
    try:
        output = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return bool(output.strip())


def _output_record(table: Table, path: Path, rows: int, nulls: dict[str, int]) -> dict:
    return {
        "name": table.name,
        "filename": path.name,
        "rows": rows,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "grain": table.grain,
        "keys": list(table.keys),
        "columns": [
            {"name": column.name, "type": column.logical_type, "nullable": column.nullable}
            for column in table.columns
        ],
        "nulls": nulls,
    }


def _profile(connection: duckdb.DuckDBPyConnection, table: Table, path: Path, kind: str) -> tuple[int, dict[str, int]]:
    if kind == "parquet":
        source = f"read_parquet('{path.as_posix()}')"
    else:
        source = _csv_relation(path)
    counts = ", ".join(
        f"count(*) filter (where {_quote(column.name)} is null) as {_quote(column.name)}"
        for column in table.columns
    )
    row = connection.execute(f"select count(*) as rows, {counts} from {source}").fetchone()
    rows = int(row[0])
    nulls = {column.name: int(row[index + 1]) for index, column in enumerate(table.columns)}
    return rows, nulls


def _data_fingerprint(outputs: list[dict]) -> str:
    names = {table.filename for table in REFERENCE_TABLES}
    lines = [
        f"{item['filename']} {item['sha256']}"
        for item in sorted(outputs, key=lambda item: item["filename"])
        if item["filename"] in names
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _file_output(path: Path, name: str, grain: str) -> dict:
    return {
        "name": name,
        "filename": path.name,
        "rows": None,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "grain": grain,
        "keys": [],
        "nulls": {},
    }


def publish_bundle(mart: Path, manifest: dict, previous: Path | None) -> dict:
    """Stage, verify and only then replace the zip in the mart directory."""
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    connection = _connect()
    outputs: list[dict] = []
    parquet_outputs: list[dict] = []
    try:
        manifest = dict(manifest)
        manifest["comparison"] = write_comparison(mart, previous, STAGING)
        for table in REFERENCE_TABLES:
            parquet = mart / table.parquet
            _export_csv(connection, table, parquet, STAGING / table.filename)
        parquet_rows: dict[str, int] = {}
        for table in PARQUET_TABLES:
            path = mart / table.parquet
            rows, nulls = _profile(connection, table, path, "parquet")
            parquet_outputs.append(_output_record(table, path, rows, nulls))
            parquet_rows[table.name] = rows
        for table in REFERENCE_TABLES:
            path = STAGING / table.filename
            rows, nulls = _profile(connection, table, path, "csv")
            if rows != parquet_rows[table.name]:
                raise ValidationError([f"{table.filename} has {rows} rows and {table.parquet} has {parquet_rows[table.name]}"])
            outputs.append(_output_record(table, path, rows, nulls))
        for table in (table for table in TABLES if table.parquet is None):
            path = STAGING / table.filename
            rows, nulls = _profile(connection, table, path, "csv")
            outputs.append(_output_record(table, path, rows, nulls))
    finally:
        connection.close()

    (STAGING / "data_dictionary.md").write_text(dictionary_markdown(), encoding="utf-8", newline="\n")
    (STAGING / "coverage.md").write_text(coverage_markdown(manifest), encoding="utf-8", newline="\n")
    year = str(manifest.get("built_at") or "0000")[:4]
    (STAGING / "ATTRIBUTION.md").write_text(
        attribution_markdown(int(year) if year.isdigit() else 0),
        encoding="utf-8",
        newline="\n",
    )
    for name, grain in (
        ("data_dictionary.md", "Column definitions for this schema version."),
        ("coverage.md", "Coverage, exclusions and source currency for this build."),
        ("ATTRIBUTION.md", "Licence and attribution."),
        ("release_diff.json", "Summary of the comparison with the previous release."),
    ):
        outputs.append(_file_output(STAGING / name, name.replace(".", "_"), grain))

    manifest["outputs"] = outputs
    manifest["parquet"] = parquet_outputs
    manifest["dictionary"] = "data_dictionary.md"
    manifest["row_counts"] = {
        item["name"]: item["rows"]
        for item in outputs
        if item.get("rows") is not None
    }
    manifest["data_fingerprint"] = _data_fingerprint(outputs)
    manifest["schema_version"] = manifest.get("schema_version") or SCHEMA_VERSION
    manifest["contract_sha256"] = contract_sha256()
    manifest["worktree_dirty"] = worktree_dirty()
    manifest["commit"] = manifest.get("commit") or git_commit()
    manifest["validation"] = {
        "conflicts": (manifest.get("validation") or {}).get("conflicts", 0),
        "bundle": "passed",
    }
    manifest_path = STAGING / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    BUILD.mkdir(parents=True, exist_ok=True)
    zip_tmp = BUILD / f".{BUNDLE_ZIP}.partial"
    with zipfile.ZipFile(zip_tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in BUNDLE_FILES:
            archive.write(STAGING / name, name)
    try:
        verify_zip(zip_tmp, mart)
    except Exception:
        zip_tmp.unlink(missing_ok=True)
        raise
    (mart / "manifest.json").write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
    target = mart / BUNDLE_ZIP
    zip_tmp.replace(target)
    digest = _sha256(target)
    (mart / BUNDLE_SHA).write_text(f"{digest}  {BUNDLE_ZIP}\n", encoding="utf-8", newline="\n")
    (BUILD / "build_id.txt").write_text(manifest["build_id"] + "\n", encoding="utf-8")
    (BUILD / "bundle_sha256.txt").write_text(digest + "\n", encoding="utf-8")
    manifest["bundle_sha256"] = digest
    return manifest


def _invalid_type(column: Column) -> str | None:
    quoted = _quote(column.name)
    blank = f"nullif(trim({quoted}), '') is null"
    present = f"nullif(trim({quoted}), '') is not null"
    value = f"trim({quoted})"
    checks: list[str] = []
    if not column.nullable:
        checks.append(blank)
    if column.logical_type == "date":
        checks.append(
            f"({present} and ("
            f"not regexp_full_match({value}, '[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}') "
            f"or try_cast({value} as date) is null))"
        )
    elif column.logical_type == "boolean":
        checks.append(f"({present} and lower({value}) not in ('true', 'false'))")
    elif column.logical_type == "integer":
        checks.append(f"({present} and not regexp_full_match({value}, '-?[0-9]+'))")
    if not checks:
        return None
    return f"count(*) filter (where {' or '.join(checks)})"


def _fail_types(
    connection: duckdb.DuckDBPyConnection,
    table: Table,
    source: str,
    failures: list[str],
) -> None:
    selects: list[str] = []
    names: list[str] = []
    for column in table.columns:
        expression = _invalid_type(column)
        if expression is None:
            continue
        selects.append(f"{expression} as {_quote(column.name)}")
        names.append(column.name)
    if not selects:
        return
    found = connection.execute(f"select {', '.join(selects)} from {source}").fetchone()
    for name, count in zip(names, found or ()):
        if count:
            failures.append(f"{table.filename} column {name} has {count} values that do not match its type")


def _fail_keys(connection: duckdb.DuckDBPyConnection, table: Table, source: str, failures: list[str]) -> None:
    by_name = {column.name: column for column in table.columns}
    key_list = ", ".join(_quote(key) for key in table.keys)
    required = [key for key in table.keys if not by_name[key].nullable]
    duplicates = connection.execute(
        f"""
        select count(*) from (
            select {key_list}
            from {source}
            group by {key_list}
            having count(*) > 1
        )
        """
    ).fetchone()[0]
    if duplicates:
        failures.append(f"{table.filename} has {duplicates} duplicate keys")
    if not required:
        return
    blank = " or ".join(f"{_quote(key)} is null or trim({_quote(key)}) = ''" for key in required)
    empty_keys = connection.execute(f"select count(*) from {source} where {blank}").fetchone()[0]
    if empty_keys:
        failures.append(f"{table.filename} has {empty_keys} blank keys")


def _normalise_value(column_name: str, logical_type: str) -> str:
    """Text form used to compare a CSV cell with the Parquet value.

    Booleans are case-folded. Every other type, including integers, compares
    as the text of the exported value.
    """
    quoted = _quote(column_name)
    if logical_type == "boolean":
        return f"lower(cast({quoted} as varchar))"
    return f"cast({quoted} as varchar)"


def verify_zip(zip_path: Path, parquet_dir: Path | None = None) -> dict:
    """Check one zip. Raises ValidationError with a specific reason."""
    if not zip_path.exists():
        raise ValidationError([f"{zip_path.name} is missing"])
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(zip_path) as archive:
            names = set(archive.namelist())
            missing = [name for name in BUNDLE_FILES if name not in names]
            if missing:
                raise ValidationError(["bundle is missing " + ", ".join(missing)])
            archive.extractall(root)
        manifest_path = root / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError([f"manifest.json is not valid JSON ({exc})"]) from exc
        version = str(manifest.get("schema_version") or "")
        if not supported_schema(version):
            raise ValidationError([
                f"unsupported schema version {version or '(missing)'}; "
                f"this checker supports major version 1"
            ])
        outputs = {item.get("filename"): item for item in manifest.get("outputs") or []}
        for name in BUNDLE_FILES:
            if name == "manifest.json":
                continue
            item = outputs.get(name)
            path = root / name
            if item is None:
                failures.append(f"manifest has no output record for {name}")
                continue
            actual = _sha256(path)
            if item.get("sha256") != actual:
                failures.append(f"{name} checksum does not match the manifest")
            if item.get("bytes") != path.stat().st_size:
                failures.append(f"{name} size does not match the manifest")
        connection = _connect()
        try:
            loaded: dict[str, str] = {}
            for table in TABLES:
                path = root / table.filename
                source = _csv_relation(path)
                loaded[table.name] = source
                columns = [row[0] for row in connection.execute(f"describe select * from {source}").fetchall()]
                expected = [column.name for column in table.columns]
                if columns != expected:
                    failures.append(f"{table.filename} columns are {columns}, expected {expected}")
                    continue
                rows = int(connection.execute(f"select count(*) from {source}").fetchone()[0])
                recorded = (outputs.get(table.filename) or {}).get("rows")
                if recorded is not None and int(recorded) != rows:
                    failures.append(f"{table.filename} row count does not match the manifest")
                _fail_keys(connection, table, source, failures)
                _fail_types(connection, table, source, failures)
                recorded_columns = (outputs.get(table.filename) or {}).get("columns")
                expected_columns = [
                    {"name": column.name, "type": column.logical_type, "nullable": column.nullable}
                    for column in table.columns
                ]
                if recorded_columns is not None and recorded_columns != expected_columns:
                    failures.append(f"{table.filename} column definitions do not match the contract")
                if table.name == "entity_alias":
                    blank = connection.execute(
                        f"select count(*) from {source} where trim(alias_text) = '' or alias_text is null"
                    ).fetchone()[0]
                    if blank:
                        failures.append(f"entity_alias.csv has {blank} blank names")
            if not failures:
                _references(connection, loaded, failures)
            if parquet_dir is not None and not failures:
                _agree_with_parquet(connection, loaded, parquet_dir, failures)
        finally:
            connection.close()
    if failures:
        raise ValidationError(failures)
    return manifest


def _references(connection: duckdb.DuckDBPyConnection, loaded: dict[str, str], failures: list[str]) -> None:
    location = loaded["location"]
    entity = loaded["search_entity"]
    links = loaded["entity_site"]
    alias = loaded["entity_alias"]
    identifier = loaded["entity_identifier"]
    checks = {
        "entity_site.csv has dangling location_id values": f"""
            select count(*) from {links} as links
            anti join {location} as location on links.location_id = location.location_id
        """,
        "entity_site.csv has dangling entity_id values": f"""
            select count(*) from {links} as links
            anti join {entity} as entity on links.entity_id = entity.entity_id
        """,
        "entity_alias.csv has dangling entity_id values": f"""
            select count(*) from {alias} as alias
            anti join {entity} as entity on alias.entity_id = entity.entity_id
        """,
        "entity_identifier.csv has dangling entity_id values": f"""
            select count(*) from {identifier} as identifier
            anti join {entity} as entity on identifier.entity_id = entity.entity_id
        """,
        "a site has no site entity": f"""
            select count(*) from {location} as location
            anti join {entity} as entity
                on entity.entity_type = 'site'
                and entity.location_id = location.location_id
                and entity.entity_id = 'site:' || location.location_id
        """,
    }
    for message, query in checks.items():
        count = int(connection.execute(query).fetchone()[0])
        if count:
            failures.append(f"{message} ({count})")


def _agree_with_parquet(
    connection: duckdb.DuckDBPyConnection,
    loaded: dict[str, str],
    parquet_dir: Path,
    failures: list[str],
) -> None:
    for table in REFERENCE_TABLES:
        parquet = parquet_dir / table.parquet
        if not parquet.exists():
            failures.append(f"{table.parquet} is missing")
            continue
        projected = ", ".join(
            f"{_normalise_value(column.name, column.logical_type)} as {_quote(column.name)}"
            for column in table.columns
        )
        csv_source = loaded[table.name]
        difference = connection.execute(
            f"""
            select count(*) from (
                select {projected} from {csv_source}
                except
                select {projected} from read_parquet('{parquet.as_posix()}')
                union all
                select {projected} from read_parquet('{parquet.as_posix()}')
                except
                select {projected} from {csv_source}
            )
            """
        ).fetchone()[0]
        if difference:
            failures.append(f"{table.filename} does not match {table.parquet} ({difference} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a location reference bundle")
    parser.add_argument("command", choices=["verify"])
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--parquet", type=Path, default=None, help="Mart directory to compare with the CSV files")
    args = parser.parse_args()
    try:
        manifest = verify_zip(args.zip_path, args.parquet)
    except ValidationError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"ok {manifest.get('build_id')} schema {manifest.get('schema_version')}")


if __name__ == "__main__":
    main()
