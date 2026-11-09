from datetime import date

import duckdb
import pytest
import requests

from ingest.download import build_postcode_parquet, postcode_member, rewrite_name_csv
from ingest.sources import (
    CQC_ACTIVE,
    CQC_DEACTIVATED,
    NSPL_KEY,
    RemoteFile,
    candidate_cqc_urls,
    choose_nspl_item,
    cqc_file_date,
    cqc_links_from_html,
    discover_cqc,
    identity_unchanged,
    pick_postcode_columns,
)

LIVE_ACTIVE = (
    "https://www.cqc.org.uk/system/files/2026-11/2_November_2026_HSCA_Active_Locations.ods"
)
LIVE_DEACTIVATED = (
    "https://www.cqc.org.uk/system/files/2026-11/02_November_2026_Deactivated_Locations.ods"
)

PAGE = """
<a href="https://www.cqc.org.uk/system/files/2026-09/01_September_2026_HSCA_Active_Locations.ods">old</a>
<a href="https://www.cqc.org.uk/system/files/2026-10/01_October_2026_HSCA_Active_Locations.ods">new</a>
<a href="/system/files/2026-10/01_October_2026_Deactivated_Locations.ods">closed</a>
"""


def test_cqc_page_keeps_the_newest_file():
    found = cqc_links_from_html(PAGE)
    assert found[CQC_ACTIVE].publisher_date == "2026-10-01"
    assert found[CQC_ACTIVE].url.endswith("01_October_2026_HSCA_Active_Locations.ods")
    assert found[CQC_DEACTIVATED].url.startswith("https://www.cqc.org.uk/")


def test_cqc_fallback_includes_the_first_and_recent_days():
    urls = candidate_cqc_urls(date(2026, 10, 13), "HSCA_Active_Locations")
    assert any(url.endswith("01_October_2026_HSCA_Active_Locations.ods") for url in urls)
    assert any(url.endswith("13_October_2026_HSCA_Active_Locations.ods") for url in urls)
    assert any("/2026-09/01_September_2026_" in url for url in urls)


def test_cqc_file_date_accepts_an_unpadded_day():
    assert cqc_file_date(LIVE_ACTIVE) == date(2026, 11, 2)
    assert cqc_file_date(LIVE_DEACTIVATED) == date(2026, 11, 2)


def test_cqc_page_keeps_an_unpadded_active_file():
    page = f'<a href="{LIVE_ACTIVE}">active</a><a href="{LIVE_DEACTIVATED}">closed</a>'
    found = cqc_links_from_html(page)
    assert found[CQC_ACTIVE].publisher_date == "2026-11-02"
    assert found[CQC_ACTIVE].url == LIVE_ACTIVE
    assert found[CQC_DEACTIVATED].url == LIVE_DEACTIVATED


def test_cqc_fallback_tries_both_day_paddings():
    urls = candidate_cqc_urls(date(2026, 11, 9), "HSCA_Active_Locations")
    assert any(url.endswith("2_November_2026_HSCA_Active_Locations.ods") for url in urls)
    assert any(url.endswith("02_November_2026_HSCA_Active_Locations.ods") for url in urls)


class _PageResponse:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None


class _PageSession:
    def __init__(self, page: str):
        self.page = page
        self.heads: list[str] = []

    def get(self, url: str, timeout=None):
        return _PageResponse(self.page)

    def head(self, url: str, allow_redirects=True, timeout=None):
        self.heads.append(url)
        raise requests.RequestException("head is not required")


def test_one_cqc_file_can_be_missing_without_dropping_the_other():
    session = _PageSession(f'<a href="{LIVE_DEACTIVATED}">closed</a>')
    found = discover_cqc(session, date(2026, 11, 9), only=CQC_DEACTIVATED)
    assert found[CQC_DEACTIVATED].url == LIVE_DEACTIVATED
    assert found[CQC_DEACTIVATED].publisher_date == "2026-11-02"
    assert CQC_ACTIVE not in found
    assert session.heads == [LIVE_DEACTIVATED]

    session = _PageSession(f'<a href="{LIVE_DEACTIVATED}">closed</a>')
    with pytest.raises(RuntimeError, match="No current CQC file found for HSCA_Active_Locations"):
        discover_cqc(session, date(2026, 11, 9), only=CQC_ACTIVE)


def test_nspl_choice_ignores_user_guides_and_older_editions():
    payload = {
        "results": [
            {"name": "NSPL_User_Guide_August_2026.zip", "modified": 9, "id": "guide"},
            {"name": "NSPL_MAY_2026.zip", "modified": 8, "id": "may"},
            {"name": "NSPL_AUG_2026.zip", "modified": 3, "id": "aug"},
            {"name": "NSPL_FEB_2023_UK.zip", "modified": 99, "id": "census"},
        ]
    }
    chosen = choose_nspl_item(payload)
    assert chosen["id"] == "aug"


def test_postcode_columns_prefer_the_later_year():
    header = ["pcds", "ctry25cd", "ctry26cd", "rgn26cd", "cty26cd", "lad26cd", "icb26cd", "sicbl26cd", "doterm"]
    assert pick_postcode_columns(header)["country_code"] == "ctry26cd"


def test_name_csv_is_rewritten_without_the_year_suffix():
    text = "CTRY25CD,CTRY25NM\nE92000001,England\n"
    assert rewrite_name_csv(text) == "code,name\nE92000001,England\n"


def test_icb_name_keeps_the_ods_code():
    text = "ICB26CD,ICB26CDH,ICB26NM\nE54000032,QKS,NHS Kent and Medway\n"
    rewritten = rewrite_name_csv(text)
    assert rewritten.startswith("code,name,ods_code\n")
    assert "QKS" in rewritten


def test_postcode_parquet_keeps_the_newer_country_code(tmp_path):
    extracted = tmp_path / "postcodes.csv"
    extracted.write_text(
        "pcds,ctry25cd,ctry26cd,rgn26cd,cty26cd,lad26cd,icb26cd,sicbl26cd,doterm\n"
        "TN24 0LZ,OLD,E92000001,E12000008,E10000016,E07000001,E54000032,,\n",
        encoding="utf-8",
    )
    parquet = tmp_path / "postcodes.parquet"
    build_postcode_parquet(extracted, parquet)
    country = duckdb.sql(
        f"select country_code from read_parquet('{parquet.as_posix()}')"
    ).fetchall()[0][0]
    assert country == "E92000001"


def test_postcode_member_prefers_the_data_directory():
    names = ["Documents/NSPL_AUG_2026_UK.csv", "Data/NSPL_AUG_2026_UK.csv"]
    assert postcode_member(names) == "Data/NSPL_AUG_2026_UK.csv"


def test_unchanged_cqc_and_postcode_files_skip_download():
    current = RemoteFile(
        key=CQC_ACTIVE,
        url="https://www.cqc.org.uk/system/files/2026-10/01_October_2026_HSCA_Active_Locations.ods",
        last_modified="Fri, 02 Oct 2026 15:16:18 GMT",
    )
    previous = {"url": current.url, "last_modified": current.last_modified}
    assert identity_unchanged(current, previous)
    current.last_modified = "Mon, 01 Dec 2026 00:00:00 GMT"
    assert not identity_unchanged(current, previous)

    nspl = RemoteFile(key=NSPL_KEY, url="https://example.invalid/data", edition="NSPL_AUG_2026", modified="10")
    assert identity_unchanged(nspl, {"url": nspl.url, "edition": "NSPL_AUG_2026", "modified": "10"})
    assert not identity_unchanged(nspl, {"url": nspl.url, "edition": "NSPL_MAY_2026", "modified": "10"})
