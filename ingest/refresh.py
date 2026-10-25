"""Download, validate, build, and describe a publishable location refresh.

A failed check leaves the previous release in place. One optional source can
fall back to its last good copy so the others still publish. The workflow
sends mail after that publish, because this command reports the run as degraded.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import requests

from ingest.build import database_path, dbt_build
from ingest.convert import OUTPUT_FIELDS
from ingest.download import RAW, discover_spec, http_session, land_spec, prepare_cqc, prepare_nspl
from ingest.history import export_history, restore_history
from ingest.registry import OGL, SPECS, SourceSpec, cache_members
from ingest.sources import CQC_ACTIVE, CQC_DEACTIVATED, NSPL_KEY, RemoteFile, identity_unchanged
from ingest.validate import (
    ValidationError,
    _product,
    measure_source,
    validate_marts,
    validate_raw,
    within_band,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
MART = ROOT / "data" / "mart"
BUILD = ROOT / "data" / "build"
STATUS = BUILD / "refresh-status.json"
REPORT = BUILD / "validation-report.json"
NOTES = BUILD / "release-notes.txt"
PREVIOUS = BUILD / "previous"
CACHE_NAME = "source-cache.zip"
DATED = {CQC_ACTIVE, CQC_DEACTIVATED, NSPL_KEY}


@dataclass
class Landed:
    spec: SourceSpec
    remote: RemoteFile | None
    status: str
    rows: int | None = None
    error: str | None = None
    stale_since: str | None = None


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def repository() -> str:
    if os.environ.get("LOCATIONS_DATA_REPO"):
        return os.environ["LOCATIONS_DATA_REPO"]
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    payload = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
    return payload["repo"]


def release_tag() -> str:
    payload = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
    return payload["tag"]


def _asset_url(name: str) -> str:
    return f"https://github.com/{repository()}/releases/download/{release_tag()}/{name}"


def _download_asset(session: requests.Session, name: str, dest: Path) -> bool:
    response = session.get(_asset_url(name), timeout=(30, 600), allow_redirects=True)
    if response.status_code == 404:
        dest.unlink(missing_ok=True)
        return False
    response.raise_for_status()
    if "text/html" in response.headers.get("Content-Type", ""):
        dest.unlink(missing_ok=True)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)
    return True


def previous_manifest(session: requests.Session) -> dict | None:
    dest = PREVIOUS / "manifest.json"
    if not _download_asset(session, "manifest.json", dest):
        print("no previous release", flush=True)
        return None
    return json.loads(dest.read_text(encoding="utf-8"))


def _previous_source(manifest: dict | None, key: str) -> dict | None:
    if not manifest:
        return None
    for item in manifest.get("sources", []):
        if item.get("key") == key:
            return item
    return None


def _previous_rows(manifest: dict | None, spec: SourceSpec) -> int | None:
    if not manifest:
        return None
    relative, _header = _product(spec)
    raw = (manifest.get("raw_counts") or {}).get(relative)
    if raw:
        return int(raw)
    old = _previous_source(manifest, spec.key)
    if old and old.get("rows"):
        return int(old["rows"])
    return None


def _same(spec: SourceSpec, remote: RemoteFile | None, old: dict | None) -> bool:
    if remote is None or old is None:
        return False
    if spec.kind in {"cqc", "nspl"}:
        return identity_unchanged(remote, old)
    return bool(remote.sha256) and old.get("sha256") == remote.sha256


def _placeholder(spec: SourceSpec) -> None:
    relative, header = _product(spec)
    dest = RAW / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    if spec.converter:
        fields = OUTPUT_FIELDS[spec.converter]
        with dest.open("w", encoding="utf-8", newline="") as handle:
            csv.DictWriter(handle, fieldnames=fields, lineterminator="\n").writeheader()
        return
    width = max(spec.minimum_columns, 1)
    dest.write_text(",".join([""] * width) + "\n", encoding="utf-8")


def _restore_spec(bundle: Path, spec: SourceSpec) -> bool:
    if not bundle.exists():
        return False
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        wanted = [name.replace("\\", "/") for name in spec.cache]
        if any(name not in names for name in wanted):
            return False
        for name in wanted:
            dest = RAW / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(archive.read(name))
    print(f"restored {spec.key} from the last good copy", flush=True)
    return True


def _write_cache(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in cache_members():
            path = RAW / relative
            if path.exists() and path.stat().st_size > 0:
                archive.write(path, relative.replace("\\", "/"))
    print(f"wrote {dest.name}", flush=True)


def _remote_from_previous(spec: SourceSpec, old: dict | None) -> RemoteFile | None:
    if not old:
        return None
    return RemoteFile(
        key=spec.key,
        url=old.get("url") or "",
        publisher_date=old.get("publisher_date"),
        edition=old.get("edition"),
        modified=old.get("modified"),
        last_modified=old.get("last_modified"),
        etag=old.get("etag"),
        sha256=old.get("sha256"),
        size=old.get("bytes"),
    )


def _accept(spec: SourceSpec, remote: RemoteFile, previous: dict | None) -> Landed:
    rows = measure_source(RAW, spec)
    if not within_band(rows, _previous_rows(previous, spec), spec.row_band, spec.row_band_floor):
        raise ValidationError([
            f"{spec.key} rows moved outside {spec.row_band:.0%} of {_previous_rows(previous, spec)}"
        ])
    return Landed(spec, remote, "ok", rows=rows)


def _fail(spec: SourceSpec, previous: dict | None, cache: Path, error: str) -> Landed:
    print(f"fallback {spec.key}: {error}", flush=True)
    old = _previous_source(previous, spec.key)
    if _restore_spec(cache, spec):
        try:
            rows = measure_source(RAW, spec)
        except ValidationError:
            rows = None
        stale = (old or {}).get("stale_since") or date.today().isoformat()
        return Landed(spec, _remote_from_previous(spec, old), "fallback", rows=rows, error=error, stale_since=stale)
    if not spec.required:
        _placeholder(spec)
    return Landed(spec, None, "missing", error=error)


def _source_record(item: Landed) -> dict:
    remote = item.remote
    return {
        "key": item.spec.key,
        "nation": item.spec.nation,
        "publisher": item.spec.publisher,
        "licence": OGL,
        "url": remote.url if remote else None,
        "publisher_date": remote.publisher_date if remote else None,
        "edition": remote.edition if remote else None,
        "modified": remote.modified if remote else None,
        "last_modified": remote.last_modified if remote else None,
        "etag": remote.etag if remote else None,
        "sha256": remote.sha256 if remote else None,
        "bytes": remote.size if remote else None,
        "rows": item.rows,
        "status": item.status,
        "stale_since": item.stale_since,
        "error": item.error,
    }


def _hospital_review() -> str | None:
    path = ROOT / "dbt" / "seeds" / "ni_hsc_hospitals.csv"
    if not path.exists():
        return None
    with path.open(encoding="utf-8", newline="") as handle:
        stamps = [row["checked_on"] for row in csv.DictReader(handle) if row.get("checked_on")]
    if not stamps:
        return None
    checked = datetime.strptime(min(stamps), "%Y-%m-%d").date()
    if (date.today() - checked).days <= 365:
        return None
    checked_label = checked.strftime("%d %B %Y").lstrip("0")
    return (
        f"The Northern Ireland hospital list was last checked on {checked_label} "
        "and is due a review."
    )


def _country_sentence() -> str:
    location = (MART / "location.parquet").as_posix()
    connection = duckdb.connect()
    try:
        pairs = connection.sql(
            f"""
            select country_name, count(*)
            from read_parquet('{location}')
            group by 1
            order by 2 desc
            """
        ).fetchall()
    finally:
        connection.close()
    parts = [f"{count:,} {country}" for country, count in pairs]
    return "Current sites: " + ", ".join(parts) + "."


def _notes(manifest: dict, landed: list[Landed]) -> str:
    stale = [item for item in landed if item.status == "fallback"]
    missing = [item for item in landed if item.status == "missing"]
    lines = [
        f"Location reference built {manifest['built_at']}.",
        _country_sentence(),
    ]
    if stale:
        names = ", ".join(f"{item.spec.publisher} ({item.spec.key})" for item in stale)
        lines.append(f"Stale sources, last good copy kept: {names}.")
    if missing:
        names = ", ".join(f"{item.spec.publisher} ({item.spec.key})" for item in missing)
        lines.append(f"Sources left out of this build: {names}.")
    review = _hospital_review()
    if review:
        lines.append(review)
    return " ".join(lines)


def _manifest(landed: list[Landed], raw_counts: dict, row_counts: dict) -> dict:
    nspl = next((item.remote.edition for item in landed if item.spec.kind == "nspl" and item.remote), None)
    return {
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "nspl_edition": nspl,
        "sources": [_source_record(item) for item in landed],
        "raw_counts": raw_counts,
        "row_counts": row_counts,
    }


def _finish(action: str, reason: str, report: dict, degraded: bool = False, stale: list[str] | None = None) -> None:
    write_json(STATUS, {
        "action": action,
        "reason": reason,
        "degraded": degraded,
        "stale": stale or [],
    })
    write_json(REPORT, report)
    print(f"{action}: {reason}", flush=True)


def _unchanged(session: requests.Session, previous: dict, force: bool) -> bool:
    """Skip the large files when every discovered source still matches."""
    if force:
        return False
    discovered: dict[str, RemoteFile] = {}
    for spec in SPECS:
        if spec.kind not in {"cqc", "nspl"}:
            continue
        try:
            discovered[spec.key] = discover_spec(session, spec)
        except Exception:
            return False
        if not identity_unchanged(discovered[spec.key], _previous_source(previous, spec.key)):
            return False
    for spec in SPECS:
        if spec.key in DATED:
            continue
        try:
            remote = land_spec(session, spec, refresh=True)
            measure_source(RAW, spec)
        except Exception:
            return False
        if not _same(spec, remote, _previous_source(previous, spec.key)):
            return False
    return True


def run(force: bool) -> None:
    session = http_session()
    previous = previous_manifest(session)
    cache = PREVIOUS / CACHE_NAME
    _download_asset(session, CACHE_NAME, cache)
    if previous and _unchanged(session, previous, force):
        _finish("skip", "sources unchanged", {"ok": True, "action": "skip", "reason": "sources unchanged"})
        return

    fetched: list[tuple[SourceSpec, RemoteFile | None, str | None]] = []
    for spec in SPECS:
        try:
            fetched.append((spec, land_spec(session, spec, refresh=True), None))
        except Exception as exc:
            fetched.append((spec, None, str(exc)))
    if all(remote is not None for spec, remote, _error in fetched if spec.kind == "cqc"):
        prepare_cqc(refresh=True)
    if all(remote is not None for spec, remote, _error in fetched if spec.kind == "nspl"):
        prepare_nspl(refresh=True)
    landed: list[Landed] = []
    for spec, remote, error in fetched:
        if error is not None or remote is None:
            landed.append(_fail(spec, previous, cache, error or "download failed"))
            continue
        try:
            landed.append(_accept(spec, remote, previous))
        except Exception as exc:
            landed.append(_fail(spec, previous, cache, str(exc)))
    fatal = [item for item in landed if item.status == "missing" and item.spec.required]
    if fatal:
        failures = [f"{item.spec.key}: {item.error}" for item in fatal]
        _finish("fail", "required sources failed", {"ok": False, "failures": failures})
        raise SystemExit(1)
    waived = {item.spec.key for item in landed if item.status == "missing"}
    try:
        raw_counts = validate_raw(RAW, waived)
    except ValidationError as exc:
        _finish("fail", "raw checks failed", {"ok": False, "failures": exc.failures})
        raise SystemExit(1) from exc

    history = PREVIOUS / "location_history.parquet"
    _download_asset(session, "location_history.parquet", history)
    database = database_path(fixtures=False)
    for path in (database, Path(str(database) + ".wal")):
        path.unlink(missing_ok=True)
    restore_history(database, history)
    try:
        dbt_build(fixtures=False)
    except SystemExit as exc:
        _finish("fail", "dbt build failed", {"ok": False, "failures": [str(exc)]})
        raise
    export_history(database, MART / "location_history.parquet")
    nations = {}
    for item in landed:
        nations.setdefault(item.spec.nation, set()).add(item.status)
    waived_countries = {
        nation for nation, statuses in nations.items() if statuses == {"missing"}
    }
    try:
        row_counts = validate_marts(MART, previous, force, waived_countries)
    except ValidationError as exc:
        _finish("fail", "mart checks failed", {"ok": False, "failures": exc.failures})
        raise SystemExit(1) from exc
    manifest = _manifest(landed, raw_counts, row_counts)
    write_json(MART / "manifest.json", manifest)
    NOTES.write_text(_notes(manifest, landed) + "\n", encoding="utf-8")
    _write_cache(MART / CACHE_NAME)
    stale = [item.spec.key for item in landed if item.status != "ok"]
    _finish(
        "publish",
        "marts passed checks",
        {"ok": True, "action": "publish", "row_counts": row_counts, "failures": [], "stale": stale},
        degraded=bool(stale),
        stale=stale,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh and validate location data")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even when sources are unchanged, and allow a large row-count change",
    )
    args = parser.parse_args()
    try:
        run(force=args.force or _enabled("FORCE_REFRESH"))
    except ValidationError as exc:
        _finish("fail", "checks failed", {"ok": False, "failures": exc.failures})
        raise SystemExit(1) from exc
    except SystemExit:
        raise
    except Exception as exc:
        _finish("fail", "refresh failed", {"ok": False, "failures": [str(exc)]})
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
