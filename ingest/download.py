"""Download public register files into data/raw.

ODS predefined reports, CQC location spreadsheets, and the ONS National
Statistics Postcode Lookup. Raw files stay out of git.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import zipfile
from pathlib import Path

import duckdb
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ingest.cqc_spreadsheet import ACTIVE_COLUMNS, DEACTIVATED_COLUMNS, convert_locations
from ingest.sources import (
    CQC_ACTIVE,
    CQC_DEACTIVATED,
    NSPL_KEY,
    RemoteFile,
    canonical_name_indexes,
    discover_sources,
    pick_postcode_columns,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
NAME_CODES = ("CTRY", "CTY", "ICB", "LAD", "RGN")
MIN_BYTES = {
    "ods/etr.csv": 1_000,
    "ods/ets.csv": 10_000,
    "ods/ephp.csv": 1_000,
    "ods/ephpsite.csv": 10_000,
    "ods/eother.csv": 1_000,
    CQC_ACTIVE: 1_000_000,
    CQC_DEACTIVATED: 1_000_000,
    NSPL_KEY: 50_000_000,
}


def http_session() -> requests.Session:
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers["User-Agent"] = "healthcare-location-reference/0.1"
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(
    session: requests.Session,
    url: str,
    dest: Path,
    minimum: int,
    refresh: bool,
) -> tuple[str, int, str | None, str | None]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size >= minimum and not refresh:
        print(f"skip {dest.relative_to(ROOT)}", flush=True)
        return sha256_file(dest), dest.stat().st_size, None, None
    print(f"get  {dest.relative_to(ROOT)}", flush=True)
    partial = dest.with_suffix(dest.suffix + ".part")
    try:
        with session.get(url, stream=True, timeout=(30, 600)) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type and dest.suffix != ".csv":
                raise RuntimeError(f"{url} returned HTML instead of a data file")
            last_modified = response.headers.get("Last-Modified")
            etag = response.headers.get("ETag")
            with partial.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        size = partial.stat().st_size
        if size < minimum:
            raise RuntimeError(f"{dest.name} is {size} bytes, below {minimum}")
        partial.replace(dest)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return sha256_file(dest), dest.stat().st_size, etag, last_modified


def apply_download(
    session: requests.Session,
    item: RemoteFile,
    refresh: bool,
) -> RemoteFile:
    digest, size, etag, modified = download_file(
        session,
        item.url,
        RAW / item.key,
        MIN_BYTES[item.key],
        refresh,
    )
    item.sha256 = digest
    item.size = size
    item.etag = etag or item.etag
    item.last_modified = modified or item.last_modified
    return item


def prepare_cqc(refresh: bool) -> None:
    outputs = {
        RAW / CQC_ACTIVE: (RAW / "cqc" / "locations.csv", ACTIVE_COLUMNS),
        RAW / CQC_DEACTIVATED: (RAW / "cqc" / "deactivated_locations.csv", DEACTIVATED_COLUMNS),
    }
    for source, (dest, columns) in outputs.items():
        if dest.exists() and dest.stat().st_size > 0 and not refresh:
            print(f"skip {dest.relative_to(ROOT)}", flush=True)
            continue
        print(f"convert {source.name}", flush=True)
        count = convert_locations(source, dest, columns)
        print(f"wrote {dest.relative_to(ROOT)} ({count} rows)", flush=True)


def _name_code(member: str) -> str | None:
    base = member.split("/")[-1]
    for code in NAME_CODES:
        if base.startswith(code + " "):
            return code
    return None


def postcode_member(names: list[str]) -> str:
    matches = [name for name in names if re.search(r"(^|/)NSPL_.*_UK\.csv$", name)]
    preferred = [name for name in matches if "/Data/" in f"/{name}"]
    chosen = preferred or matches
    if len(chosen) != 1:
        raise RuntimeError(f"Expected one UK postcode file, found {chosen}")
    return chosen[0]


def rewrite_name_csv(text: str) -> str:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise RuntimeError("Geography name file is empty")
    indexes = canonical_name_indexes(rows[0])
    fields = ["code", "name"] + (["ods_code"] if "ods_code" in indexes else [])
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        record = {
            field: row[indexes[field]].strip() if indexes[field] < len(row) else ""
            for field in fields
        }
        if record["code"] and record["name"]:
            writer.writerow(record)
    return buffer.getvalue()


def _extract_names(bundle: zipfile.ZipFile, refresh: bool) -> None:
    dest_dir = RAW / "ons" / "names"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in bundle.namelist():
        code = _name_code(name)
        if code is None or not name.endswith(".csv"):
            continue
        dest = dest_dir / f"{code}.csv"
        if dest.exists() and dest.stat().st_size > 0 and not refresh:
            continue
        text = bundle.read(name).decode("utf-8-sig")
        dest.write_text(rewrite_name_csv(text), encoding="utf-8")
        print(f"wrote {dest.relative_to(ROOT)}", flush=True)


def _header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def build_postcode_parquet(extracted: Path, parquet: Path) -> None:
    header = _header(extracted)
    lookup = {name.lower(): name for name in header}
    if "pcds" not in lookup:
        raise RuntimeError("Postcode file has no pcds column")
    columns = pick_postcode_columns(header)
    doterm = lookup.get("doterm")
    order = (
        f"case when \"{doterm}\" is null or \"{doterm}\" = '' then 0 else 1 end"
        if doterm
        else "0"
    )
    selects = [
        f"upper(replace(\"{lookup['pcds']}\", ' ', '')) as postcode_compact",
    ]
    for alias, source in columns.items():
        selects.append(f"nullif(\"{source}\", '') as {alias}")
    print("build postcode parquet", flush=True)
    duckdb.sql(
        f"""
        copy (
            select {", ".join(selects)}
            from read_csv('{extracted.as_posix()}', header = true, all_varchar = true)
            where \"{lookup['pcds']}\" is not null and \"{lookup['pcds']}\" <> ''
            qualify row_number() over (
                partition by upper(replace(\"{lookup['pcds']}\", ' ', ''))
                order by {order}
            ) = 1
        ) to '{parquet.as_posix()}' (format parquet)
        """
    )
    print(f"wrote {parquet.name}", flush=True)


def prepare_nspl(refresh: bool) -> None:
    archive = RAW / NSPL_KEY
    parquet = RAW / "ons" / "postcodes.parquet"
    with zipfile.ZipFile(archive) as bundle:
        _extract_names(bundle, refresh)
        if parquet.exists() and parquet.stat().st_size > 0 and not refresh:
            print(f"skip {parquet.relative_to(ROOT)}", flush=True)
            return
        member = postcode_member(bundle.namelist())
        extracted = RAW / "ons" / Path(member).name
        if not extracted.exists() or refresh:
            print("unzip postcode directory", flush=True)
            extracted.write_bytes(bundle.read(member))
    build_postcode_parquet(extracted, parquet)
    extracted.unlink(missing_ok=True)


def fetch_all(session: requests.Session, refresh: bool, today=None) -> dict[str, RemoteFile]:
    found = discover_sources(session, today)
    for item in found.values():
        apply_download(session, item, refresh)
    prepare_cqc(refresh)
    prepare_nspl(refresh)
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public location registers")
    parser.add_argument("--refresh", action="store_true", help="Download again even if present")
    args = parser.parse_args()
    fetch_all(http_session(), args.refresh)


if __name__ == "__main__":
    main()
