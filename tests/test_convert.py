import csv
from datetime import date
from pathlib import Path

from openpyxl import Workbook

from ingest.convert import convert_care_inspectorate, convert_ciw, convert_rqia
from ingest.sources import choose_ckan_resource, datastore_date


def test_ciw_keeps_adult_care_and_drops_person_columns(tmp_path: Path):
    source = tmp_path / "ciw.csv"
    source.write_text(
        "Service URN,Service name,Known as,Service type,Service sub-type,"
        "Service address line 1,Service town/city,Service postcode,Provider name,Manager name\n"
        "SIN-1,Adult Home,,Care Home Service,Adults With Nursing,Road,Cardiff,CF10 1AA,Provider,A Person\n"
        "SIN-2,Child Home,,Care Home Service,Childrens Home,Road,Cardiff,CF10 1AA,Provider,A Person\n",
        encoding="utf-8",
    )
    dest = tmp_path / "out.csv"
    assert convert_ciw(source, dest) == 1
    with dest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["service_urn"] == "SIN-1"
    assert "Manager name" not in rows[0]
    assert "manager" not in "".join(rows[0].values()).lower()


def test_care_inspectorate_keeps_active_adult_services(tmp_path: Path):
    source = tmp_path / "cis.csv"
    source.write_text(
        "CSNumber,CareService,Subtype,ServiceName,Service_Postcode,ServiceStatus,Manager_Name\n"
        "CS1,Support Service,Care at Home,Home Care,EH1 2NG,Active,A Person\n"
        "CS2,Child Minding,Childminding,A Childminder,EH1 2NG,Active,A Person\n"
        "CS3,Care Home Service,Older People,Closed Home,EH1 2NG,Inactive,A Person\n",
        encoding="utf-8",
    )
    dest = tmp_path / "out.csv"
    assert convert_care_inspectorate(source, dest) == 1
    with dest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["service_id"] == "CS1"
    assert "Manager_Name" not in rows[0]


def test_rqia_reads_the_header_below_the_title(tmp_path: Path):
    source = tmp_path / "rqia.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Register as at 08/06/26"])
    sheet.append([])
    sheet.append(["Service ID", "Service", "Address Line1", "Address Line2", "Town", "Postcode", "Phone", "", "Category", "Responsible Person", "Manager", "Provider"])
    sheet.append(["1", "Example Home", "Road", "", "Belfast", "BT12 6BA", "028", "", "Nursing (NH)", "A Person", "A Manager", "Example Provider"])
    sheet.append(["2", "Day Centre", "Road", "", "Belfast", "BT12 6BA", "028", "", "Day Care Setting", "A Person", "A Manager", "Example Provider"])
    workbook.save(source)
    dest = tmp_path / "out.csv"
    assert convert_rqia(source, dest) == 1
    with dest.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["service_id"] == "1"
    assert row["category"] == "Nursing (NH)"
    assert "A Person" not in row.values()


def test_ckan_prefers_the_newest_csv():
    chosen = choose_ckan_resource(
        [
            {"name": "old.csv", "url": "https://example.invalid/old.csv", "format": "CSV", "created": "2026-01-01"},
            {"name": "notes.pdf", "url": "https://example.invalid/notes.pdf", "format": "PDF", "created": "2026-09-01"},
            {"name": "new.csv", "url": "https://example.invalid/new.csv", "format": "CSV", "created": "2026-07-01"},
        ],
        r"csv|notes",
    )
    assert chosen["name"] == "new.csv"


def test_datastore_dates():
    assert datastore_date("datastore-31-august-2026") == date(2026, 8, 31)
    assert datastore_date("datastore-31-08-2025") == date(2025, 8, 31)
    assert datastore_date("datastore-30nov2025") == date(2025, 11, 30)
