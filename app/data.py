"""Locate the location files: a local build, the published release, or the sample."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"
RELEASE = json.loads((ROOT / "release.json").read_text(encoding="utf-8"))
ASSETS = (
    "location.parquet",
    "search_entity.parquet",
    "entity_site.parquet",
    "manifest.json",
)
SAMPLE_WARNING = (
    "Showing the bundled sample, because the published location files could not be downloaded."
)


@dataclass(frozen=True)
class LocationData:
    directory: Path
    source: str
    manifest: dict

    @property
    def location(self) -> Path:
        return self.directory / "location.parquet"

    @property
    def search(self) -> Path:
        return self.directory / "search_entity.parquet"

    @property
    def links(self) -> Path:
        return self.directory / "entity_site.parquet"


def load_manifest(directory: Path) -> dict:
    path = directory / "manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _complete(directory: Path) -> bool:
    return all((directory / name).exists() and (directory / name).stat().st_size > 0 for name in ASSETS[:3])


def _repository() -> str:
    return os.environ.get("LOCATIONS_DATA_REPO") or RELEASE["repo"]


def _asset_url(name: str) -> str:
    return f"https://github.com/{_repository()}/releases/download/{RELEASE['tag']}/{name}"


def _download_release() -> Path | None:
    cache = Path(os.environ.get("LOCATIONS_CACHE_DIR", Path.home() / ".cache" / "healthcare-location-reference"))
    staging = cache.with_name(cache.name + ".partial")
    session = requests.Session()
    session.headers["User-Agent"] = "healthcare-location-reference/0.1"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        for name in ASSETS:
            response = session.get(_asset_url(name), timeout=(30, 600), allow_redirects=True)
            response.raise_for_status()
            if "text/html" in response.headers.get("Content-Type", ""):
                raise RuntimeError(f"{name} was not a data file")
            target = staging / name
            target.write_bytes(response.content)
            if name.endswith(".parquet") and target.stat().st_size < 1_000_000:
                raise RuntimeError(f"{name} is too small to be the published mart")
    except (requests.RequestException, OSError, RuntimeError):
        shutil.rmtree(staging, ignore_errors=True)
        return None
    if cache.exists():
        shutil.rmtree(cache)
    staging.rename(cache)
    return cache


def resolve_data() -> LocationData:
    override = os.environ.get("LOCATIONS_MART_DIR")
    if override:
        directory = Path(override)
        if not _complete(directory):
            raise FileNotFoundError(f"Location files are missing in {directory}")
        return LocationData(directory, "local", load_manifest(directory))
    local = ROOT / "data" / "mart"
    if _complete(local):
        return LocationData(local, "local", load_manifest(local))
    downloaded = _download_release()
    if downloaded is not None and _complete(downloaded):
        return LocationData(downloaded, "release", load_manifest(downloaded))
    if not _complete(SAMPLE):
        raise FileNotFoundError("Location files are missing, and the sample is missing too.")
    return LocationData(SAMPLE, "sample", load_manifest(SAMPLE))


@st.cache_resource(ttl=24 * 60 * 60)
def _cached_remote() -> LocationData:
    downloaded = _download_release()
    if downloaded is not None and _complete(downloaded):
        return LocationData(downloaded, "release", load_manifest(downloaded))
    return LocationData(SAMPLE, "sample", load_manifest(SAMPLE))


def ensure_data() -> LocationData:
    override = os.environ.get("LOCATIONS_MART_DIR")
    if override:
        return resolve_data()
    local = ROOT / "data" / "mart"
    if _complete(local):
        return LocationData(local, "local", load_manifest(local))
    return _cached_remote()


def _long_date(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%d %B %Y").lstrip("0")


def _built_label(manifest: dict, directory: Path) -> str:
    built = manifest.get("built_at")
    if built:
        return _long_date(built)
    location = directory / "location.parquet"
    if location.exists():
        return datetime.fromtimestamp(location.stat().st_mtime).strftime("%d %B %Y").lstrip("0")
    return ""


def edition_label(edition: str) -> str:
    months = {
        "JAN": "January",
        "FEB": "February",
        "MAR": "March",
        "APR": "April",
        "MAY": "May",
        "JUN": "June",
        "JUL": "July",
        "AUG": "August",
        "SEP": "September",
        "OCT": "October",
        "NOV": "November",
        "DEC": "December",
    }
    parts = edition.split("_")
    if len(parts) >= 3 and parts[-1].isdigit() and parts[-2] in months:
        return f"{months[parts[-2]]} {parts[-1]}"
    return edition.replace("_", " ")


def currency_markdown(data: LocationData) -> str:
    built = _built_label(data.manifest, data.directory)
    opening = f"This copy was built on {built}." if built else "This copy has no build date."
    cqc_date = None
    for source in data.manifest.get("sources", []):
        if source.get("key") == "cqc/active_locations.ods" and source.get("publisher_date"):
            cqc_date = source["publisher_date"]
    edition = data.manifest.get("nspl_edition")
    cqc = (
        f"Care Quality Commission rows come from the active-locations spreadsheet dated {_long_date(cqc_date)}."
        if cqc_date
        else "Care Quality Commission rows come from the monthly active-locations spreadsheet."
    )
    postcodes = (
        f"Area names come from the Office for National Statistics postcode lookup for {edition_label(edition)}."
        if edition
        else "Area names come from the Office for National Statistics postcode lookup."
    )
    return "\n\n".join(
        [
            opening,
            (
                "The published copy is checked on Monday at 04:00 UTC "
                "(04:00 GMT, or 05:00 during British Summer Time) and replaced when the "
                "source files have changed. A failed check keeps the previous copy. "
                "A file you built yourself is only as current as the download you used."
            ),
            cqc,
            (
                "Deactivated locations are kept for a later history view and are not searchable here. "
                + postcodes
                + " Searching a postcode lists the sites recorded at that postcode. "
                "The lookup file itself is not a list of sites."
            ),
        ]
    )


def attribution_year(manifest: dict) -> int:
    built = manifest.get("built_at") or ""
    if len(built) >= 4 and built[:4].isdigit():
        return int(built[:4])
    return datetime.now().year


def attribution_markdown(year: int) -> str:
    return (
        "NHS organisation data from NHS England, care location data from the "
        "Care Quality Commission, and postcode geography from the Office for "
        "National Statistics, used under the "
        "[Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). "
        f"Contains OS data © Crown copyright and database right {year}. "
        f"Contains Royal Mail data © Royal Mail copyright and database right {year}. "
        f"Contains National Statistics data © Crown copyright and database right {year}."
    )
