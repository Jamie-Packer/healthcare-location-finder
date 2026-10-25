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
LOCAL = ROOT / "data" / "mart"
MIN_PARQUET_BYTES = 1_000_000
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
    session.headers["User-Agent"] = "healthcare-location-reference/0.2"
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
            if name.endswith(".parquet") and target.stat().st_size < MIN_PARQUET_BYTES:
                raise RuntimeError(f"{name} is too small to be the published mart")
            if name.endswith(".json"):
                json.loads(target.read_text(encoding="utf-8"))
    except (requests.RequestException, OSError, RuntimeError, ValueError):
        shutil.rmtree(staging, ignore_errors=True)
        return None
    if cache.exists():
        shutil.rmtree(cache)
    staging.rename(cache)
    return cache


class ReleaseUnavailable(RuntimeError):
    """The published files could not be downloaded."""


def _sample() -> LocationData:
    if not _complete(SAMPLE):
        raise FileNotFoundError("Location files are missing, and the sample is missing too.")
    return LocationData(SAMPLE, "sample", load_manifest(SAMPLE))


# Streamlit does not cache a call that raises, so a failed download is retried
# on the next run instead of pinning the sample for a day.
@st.cache_resource(ttl=24 * 60 * 60, show_spinner="Loading the latest location files...")
def _cached_release() -> LocationData:
    downloaded = _download_release()
    if downloaded is None or not _complete(downloaded):
        raise ReleaseUnavailable("download failed")
    return LocationData(downloaded, "release", load_manifest(downloaded))


def ensure_data() -> LocationData:
    override = os.environ.get("LOCATIONS_MART_DIR")
    if override:
        directory = Path(override)
        if not _complete(directory):
            raise FileNotFoundError(f"Location files are missing in {directory}")
        return LocationData(directory, "local", load_manifest(directory))
    if _complete(LOCAL):
        return LocationData(LOCAL, "local", load_manifest(LOCAL))
    try:
        return _cached_release()
    except ReleaseUnavailable:
        return _sample()


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


SOURCE_LABELS = {
    "cqc/active_locations.ods": "Care Quality Commission active locations",
    "ods/etr.csv": "NHS trusts",
    "ods/ets.csv": "NHS trust sites",
    "ods/ephp.csv": "Independent healthcare providers",
    "ods/ephpsite.csv": "Independent healthcare provider sites",
    "ods/wlhb.csv": "Welsh health boards",
    "ods/wlhbsite.csv": "Welsh health board sites",
    "ods/epraccur.csv": "Welsh GP practices",
    "ciw/services.csv": "Care Inspectorate Wales services",
    "phs/hospitals.csv": "Scottish hospitals",
    "phs/gp_practices.csv": "Scottish GP practices",
    "phs/council_board.csv": "Scottish council to health board lookup",
    "care_inspectorate/services.csv": "Care Inspectorate services",
    "ods/niorg.csv": "Northern Ireland organisations",
    "ods/npraccur.csv": "Northern Ireland GP practices",
    "rqia/services.csv": "RQIA services",
}


def currency_markdown(data: LocationData) -> str:
    built = _built_label(data.manifest, data.directory)
    opening = f"This copy was built on **{built}**." if built else "This copy has no build date."
    edition = data.manifest.get("nspl_edition")
    postcodes = (
        f"Area names come from the Office for National Statistics postcode lookup for {edition_label(edition)}."
        if edition
        else "Area names come from the Office for National Statistics postcode lookup."
    )
    parts = [
        opening,
        (
            "The published copy is checked every Monday at 04:00 UTC (04:00 GMT, or 05:00 "
            "during British Summer Time) and replaced when a source has changed. A copy you "
            "build yourself is as current as the files you downloaded."
        ),
        (
            "If one source cannot be fetched, it keeps its last good copy and is marked stale "
            "below, while the other sources still update. If an England source has no saved "
            "copy, the previous release stays in place."
        ),
    ]
    sources = _source_currency(data.manifest)
    if sources:
        parts.append(sources)
    parts.append(
        postcodes + " Searching a postcode lists the sites recorded at that postcode. "
        "Deactivated locations are kept for a later history view and are not searchable yet."
    )
    return "\n\n".join(parts)


def _source_currency(manifest: dict) -> str:
    stale, dated, undated = [], [], []
    for source in manifest.get("sources", []):
        label = SOURCE_LABELS.get(source.get("key", ""))
        if label is None:
            continue
        if source.get("status") == "fallback":
            since = source.get("stale_since")
            when = f" since {_long_date(since)}" if since else ""
            stale.append(f"- **{label}** is stale{when}, so its last good copy is used.")
        elif source.get("publisher_date"):
            dated.append(f"- {label}: {_long_date(source['publisher_date'])}")
        else:
            undated.append(label)
    parts = []
    if stale:
        parts.append("**Stale sources**\n\n" + "\n".join(stale))
    if dated:
        parts.append("Publish dates of the source files:\n\n" + "\n".join(dated))
    if undated:
        parts.append("These files carry no publish date and were fetched for this build: " + ", ".join(undated) + ".")
    return "\n\n".join(parts)


def attribution_year(manifest: dict) -> int:
    built = manifest.get("built_at") or ""
    if len(built) >= 4 and built[:4].isdigit():
        return int(built[:4])
    return datetime.now().year


def attribution_markdown(year: int) -> str:
    return (
        "NHS organisation data from NHS England, care location data from the "
        "Care Quality Commission, Welsh care services from Care Inspectorate Wales, "
        "Scottish hospitals, GP practices and health board geography from Public Health Scotland, "
        "Scottish care services from the Care Inspectorate, Northern Ireland regulated "
        "services from RQIA, and postcode geography from the Office for "
        "National Statistics, used under the "
        "[Open Government Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). "
        f"Contains OS data © Crown copyright and database right {year}. "
        f"Contains Royal Mail data © Royal Mail copyright and database right {year}. "
        f"Contains National Statistics data © Crown copyright and database right {year}."
    )
