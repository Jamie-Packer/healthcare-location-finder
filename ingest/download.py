"""Download public register files into data/raw.

ODS predefined reports, CQC location spreadsheets, and the ONS National
Statistics Postcode Lookup. Raw files stay out of git.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import duckdb
import requests

from ingest.cqc_spreadsheet import ACTIVE_COLUMNS, DEACTIVATED_COLUMNS, convert_locations

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
ODS = "https://www.odsdatasearchandexport.nhs.uk/api/getReport?report={report}"

# Report ids stay as NHS England publishes them.
# etr trusts, ets trust sites, ephp independent providers,
# ephpsite independent-provider sites, eother other organisations.
FILES = {
    "ods/etr.csv": ODS.format(report="etr"),
    "ods/ets.csv": ODS.format(report="ets"),
    "ods/ephp.csv": ODS.format(report="ephp"),
    "ods/ephpsite.csv": ODS.format(report="ephpsite"),
    "ods/eother.csv": ODS.format(report="eother"),
    # The weekly directory CSV has names and service types only. Organisation
    # codes and registration dates are on the monthly active-locations sheet.
    "cqc/care_directory.csv": (
        "https://www.cqc.org.uk/system/files/2026-10/07_October_2026_CQC_directory.csv"
    ),
    "cqc/active_locations.ods": (
        "https://www.cqc.org.uk/system/files/2026-10/01_October_2026_HSCA_Active_Locations.ods"
    ),
    "cqc/deactivated_locations.ods": (
        "https://www.cqc.org.uk/system/files/2026-10/01_October_2026_Deactivated_Locations.ods"
    ),
}

NSPL_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    "9d8364ebae8b4439aa66cda440e54fc8/data"
)
NAME_PREFIXES = (
    "CTRY Country names",
    "CTY County names",
    "ICB Integrated Care Board names",
    "LAD Local Authority District names",
    "RGN Region names",
)

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "healthcare-location-reference/0.1"


def _exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def download(url: str, dest: Path, refresh: bool) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if _exists(dest) and not refresh:
        print(f"skip {dest.relative_to(ROOT)}", flush=True)
        return
    print(f"get  {dest.relative_to(ROOT)}", flush=True)
    with SESSION.get(url, stream=True, timeout=(30, 300)) as response:
        response.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def prepare_cqc(refresh: bool) -> None:
    outputs = {
        RAW / "cqc" / "active_locations.ods": (
            RAW / "cqc" / "locations.csv",
            ACTIVE_COLUMNS,
        ),
        RAW / "cqc" / "deactivated_locations.ods": (
            RAW / "cqc" / "deactivated_locations.csv",
            DEACTIVATED_COLUMNS,
        ),
    }
    for source, (dest, columns) in outputs.items():
        if _exists(dest) and not refresh:
            print(f"skip {dest.relative_to(ROOT)}", flush=True)
            continue
        print(f"convert {source.name}", flush=True)
        count = convert_locations(source, dest, columns)
        print(f"wrote {dest.relative_to(ROOT)} ({count} rows)", flush=True)


def _extract_names(bundle: zipfile.ZipFile, refresh: bool) -> None:
    dest_dir = RAW / "ons" / "names"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in bundle.namelist():
        if not name.endswith(".csv"):
            continue
        if not any(name.startswith("Documents/" + prefix) for prefix in NAME_PREFIXES):
            continue
        label = name.split("/")[-1].split(" ")[0] + ".csv"
        dest = dest_dir / label
        if _exists(dest) and not refresh:
            continue
        text = bundle.read(name).decode("utf-8-sig")
        dest.write_text(text, encoding="utf-8")
        print(f"wrote {dest.relative_to(ROOT)}", flush=True)


def prepare_nspl(refresh: bool) -> None:
    archive = RAW / "ons" / "nspl.zip"
    download(NSPL_URL, archive, refresh)
    parquet = RAW / "ons" / "postcodes.parquet"
    with zipfile.ZipFile(archive) as bundle:
        _extract_names(bundle, refresh)
        if _exists(parquet) and not refresh:
            print(f"skip {parquet.relative_to(ROOT)}", flush=True)
            return
        member = "Data/NSPL_AUG_2026_UK.csv"
        extracted = RAW / "ons" / member
        if not _exists(extracted):
            print("unzip postcode directory", flush=True)
            bundle.extract(member, RAW / "ons")
    print("build postcode parquet", flush=True)
    duckdb.sql(
        f"""
        copy (
            select
                upper(replace(pcds, ' ', '')) as postcode_compact,
                nullif(ctry26cd, '') as country_code,
                nullif(rgn26cd, '') as region_code,
                nullif(cty26cd, '') as county_code,
                nullif(lad26cd, '') as local_authority_code,
                nullif(icb26cd, '') as icb_code
            from read_csv('{extracted.as_posix()}', header = true, all_varchar = true)
            where pcds is not null and pcds <> ''
            qualify row_number() over (
                partition by upper(replace(pcds, ' ', ''))
                order by case when doterm is null or doterm = '' then 0 else 1 end
            ) = 1
        ) to '{parquet.as_posix()}' (format parquet)
        """
    )
    extracted.unlink(missing_ok=True)
    print(f"wrote {parquet.relative_to(ROOT)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public location registers")
    parser.add_argument("--refresh", action="store_true", help="Download again even if present")
    args = parser.parse_args()
    for relative, url in FILES.items():
        download(url, RAW / relative, args.refresh)
    prepare_cqc(args.refresh)
    prepare_nspl(args.refresh)


if __name__ == "__main__":
    main()
