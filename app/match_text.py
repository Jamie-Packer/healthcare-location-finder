"""Shared match-string cleanup and download naming."""

from __future__ import annotations

import re

# Keep aligned with dbt/models/marts/location.sql.
MATCH_STOPWORDS = frozenset(
    {
        "A",
        "AN",
        "AND",
        "AT",
        "FOR",
        "IN",
        "OF",
        "ON",
        "THE",
        "TO",
        "NHS",
        "TRUST",
        "FOUNDATION",
        "HOSPITAL",
        "HOSPITALS",
        "CENTRE",
        "CENTER",
        "CLINIC",
        "CLINICS",
        "LIMITED",
        "LTD",
        "PLC",
        "ROAD",
        "STREET",
        "AVENUE",
        "LANE",
        "DRIVE",
        "CLOSE",
        "WAY",
        "COURT",
        "PLACE",
    }
)


def strip_stopwords(text: object) -> str:
    return " ".join(
        token
        for token in str(text or "").upper().split()
        if token and token not in MATCH_STOPWORDS
    )


DEFAULT_COLUMNS = (
    "name",
    "parent_name",
    "town",
    "postcode",
    "country_name",
    "local_authority_name",
    "health_area_name",
    "service_type",
    "match_string",
)

ALL_COLUMNS = (
    "name",
    "parent_name",
    "address",
    "town",
    "postcode",
    "postcode_compact",
    "country_name",
    "local_authority_name",
    "local_authority_code",
    "county_name",
    "county_code",
    "region_name",
    "region_code",
    "health_area_name",
    "health_area_type",
    "health_area_code",
    "health_area_ods_code",
    "parent_code",
    "nhs_code",
    "regulator",
    "regulator_id",
    "service_type",
    "source",
    "valid_from",
    "valid_to",
    "match_string",
)


def chosen_columns(selected: object) -> tuple[str, ...]:
    """Keep the download columns in a stable order, with the keyword string last."""
    wanted = {str(name) for name in (selected or [])}
    picked = [name for name in ALL_COLUMNS if name in wanted and name != "match_string"]
    if not picked:
        picked = [name for name in DEFAULT_COLUMNS if name != "match_string"]
    picked.append("match_string")
    return tuple(picked)


def download_stem(name: object) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", str(name or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned[:150] or "locations"
