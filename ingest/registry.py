"""Every public register the refresh knows how to fetch.

Required sources are the England core. The others are fetched the same way,
and a weekly refresh can fall back to the last good copy of just that one.
"""

from __future__ import annotations

from dataclasses import dataclass

from ingest.sources import CQC_ACTIVE, CQC_DEACTIVATED, NSPL_KEY


@dataclass(frozen=True)
class SourceSpec:
    key: str
    nation: str
    publisher: str
    required: bool
    minimum_bytes: int
    minimum_rows: int
    kind: str
    cache: tuple[str, ...]
    report: str | None = None
    ckan_base: str | None = None
    ckan_package: str | None = None
    ckan_pattern: str | None = None
    converter: str | None = None
    header: bool = True
    minimum_columns: int = 1
    required_columns: tuple[str, ...] = ()
    row_band: float = 0.25
    row_band_floor: int = 40


OGL = "Open Government Licence"

ENGLAND_ODS = (
    ("ods/etr.csv", "etr", 1_000, 100, 12),
    ("ods/ets.csv", "ets", 10_000, 1_000, 15),
    ("ods/ephp.csv", "ephp", 1_000, 100, 12),
    ("ods/ephpsite.csv", "ephpsite", 10_000, 500, 15),
    ("ods/eother.csv", "eother", 1_000, 40, 12),
)


def _ods(key: str, report: str, minimum_bytes: int, minimum_rows: int, minimum_columns: int, nation: str, required: bool) -> SourceSpec:
    return SourceSpec(
        key=key,
        nation=nation,
        publisher="NHS England",
        required=required,
        minimum_bytes=minimum_bytes,
        minimum_rows=minimum_rows,
        kind="ods",
        cache=(key,),
        report=report,
        header=False,
        minimum_columns=minimum_columns,
    )


SPECS: tuple[SourceSpec, ...] = (
    *(
        _ods(key, report, size, rows, columns, "England", True)
        for key, report, size, rows, columns in ENGLAND_ODS
    ),
    SourceSpec(
        key=CQC_ACTIVE,
        nation="England",
        publisher="Care Quality Commission",
        required=True,
        minimum_bytes=1_000_000,
        minimum_rows=30_000,
        kind="cqc",
        cache=("cqc/locations.csv",),
        header=True,
        required_columns=("cqc_location_id", "name", "postcode"),
    ),
    SourceSpec(
        key=CQC_DEACTIVATED,
        nation="England",
        publisher="Care Quality Commission",
        required=True,
        minimum_bytes=1_000_000,
        minimum_rows=5_000,
        kind="cqc",
        cache=("cqc/deactivated_locations.csv",),
        header=True,
        required_columns=("cqc_location_id", "name"),
    ),
    SourceSpec(
        key=NSPL_KEY,
        nation="United Kingdom",
        publisher="Office for National Statistics",
        required=True,
        minimum_bytes=50_000_000,
        minimum_rows=1_000_000,
        kind="nspl",
        cache=(
            "ons/postcodes.parquet",
            "ons/names/CTRY.csv",
            "ons/names/CTY.csv",
            "ons/names/ICB.csv",
            "ons/names/LAD.csv",
            "ons/names/RGN.csv",
            "ons/names/SICBL.csv",
        ),
        header=False,
    ),
    _ods("ods/wlhb.csv", "wlhb", 200, 5, 10, "Wales", False),
    _ods("ods/wlhbsite.csv", "wlhbsite", 20_000, 500, 10, "Wales", False),
    _ods("ods/epraccur.csv", "epraccur", 200_000, 8_000, 20, "Wales", False),
    _ods("ods/niorg.csv", "niorg", 400, 10, 10, "Northern Ireland", False),
    _ods("ods/npraccur.csv", "npraccur", 5_000, 200, 12, "Northern Ireland", False),
    SourceSpec(
        key="ciw/services.csv",
        nation="Wales",
        publisher="Care Inspectorate Wales",
        required=False,
        minimum_bytes=500_000,
        minimum_rows=1_000,
        kind="direct",
        cache=("ciw/services.csv",),
        converter="ciw",
        required_columns=("service_urn", "name", "service_type", "postcode", "provider_name"),
    ),
    SourceSpec(
        key="phs/hospitals.csv",
        nation="Scotland",
        publisher="Public Health Scotland",
        required=False,
        minimum_bytes=5_000,
        minimum_rows=150,
        kind="ckan",
        cache=("phs/hospitals.csv",),
        ckan_base="https://www.opendata.nhs.scot",
        ckan_package="hospital-codes",
        ckan_pattern=r"hospital",
        converter="phs_hospitals",
        required_columns=("hospital_code", "name", "postcode", "health_board_code"),
    ),
    SourceSpec(
        key="phs/gp_practices.csv",
        nation="Scotland",
        publisher="Public Health Scotland",
        required=False,
        minimum_bytes=20_000,
        minimum_rows=600,
        kind="ckan",
        cache=("phs/gp_practices.csv",),
        ckan_base="https://www.opendata.nhs.scot",
        ckan_package="gp-practice-contact-details-and-list-sizes",
        ckan_pattern=r"GP Practices and List sizes",
        converter="phs_practices",
        required_columns=("practice_code", "name", "postcode", "health_board_code"),
    ),
    SourceSpec(
        key="phs/council_board.csv",
        nation="Scotland",
        publisher="Public Health Scotland",
        required=False,
        minimum_bytes=400,
        minimum_rows=20,
        kind="ckan",
        cache=("phs/council_board.csv",),
        ckan_base="https://www.opendata.nhs.scot",
        ckan_package="geography-codes-and-labels",
        ckan_pattern=r"ca11_ca19|Council Area 2011",
        converter="phs_boards",
        required_columns=("council_code", "health_board_code", "health_board_name"),
    ),
    SourceSpec(
        key="care_inspectorate/services.csv",
        nation="Scotland",
        publisher="Care Inspectorate",
        required=False,
        minimum_bytes=500_000,
        minimum_rows=2_000,
        kind="page",
        cache=("care_inspectorate/services.csv",),
        converter="care_inspectorate",
        required_columns=("service_id", "name", "service_type", "postcode"),
    ),
    SourceSpec(
        key="rqia/services.csv",
        nation="Northern Ireland",
        publisher="RQIA",
        required=False,
        minimum_bytes=50_000,
        minimum_rows=800,
        kind="page",
        cache=("rqia/services.csv",),
        converter="rqia",
        required_columns=("service_id", "name", "postcode", "category"),
    ),
)


def by_key() -> dict[str, SourceSpec]:
    return {spec.key: spec for spec in SPECS}


def cache_members() -> tuple[str, ...]:
    seen: list[str] = []
    for spec in SPECS:
        for name in spec.cache:
            if name not in seen:
                seen.append(name)
    return tuple(seen)
