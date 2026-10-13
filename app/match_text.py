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


def download_stem(name: object) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "", str(name or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned[:150] or "locations"
