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


def test_cqc_spreadsheet_preserves_nested_span_text(tmp_path: Path):
    import zipfile
    from ingest.cqc_spreadsheet import ACTIVE_COLUMNS, convert_locations

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        "<office:body><office:spreadsheet>"
        '<table:table table:name="HSCA Active Locations">'
        "<table:table-row>"
        "<table:table-cell><text:p>Location ID</text:p></table:table-cell>"
        "<table:table-cell><text:p>Location Name</text:p></table:table-cell>"
        "<table:table-cell><text:p>Location Postal Code</text:p></table:table-cell>"
        "</table:table-row>"
        "<table:table-row>"
        "<table:table-cell><text:p>1-999</text:p></table:table-cell>"
        '<table:table-cell><text:p>North <text:span>Valley</text:span><text:s/>Hospital</text:p></table:table-cell>'
        "<table:table-cell><text:p>TN24 0LZ</text:p></table:table-cell>"
        "</table:table-row>"
        "</table:table></office:spreadsheet></office:body></office:document-content>"
    )
    ods = tmp_path / "active.ods"
    with zipfile.ZipFile(ods, "w") as archive:
        archive.writestr("content.xml", xml)
    dest = tmp_path / "locations.csv"
    assert convert_locations(ods, dest, ACTIVE_COLUMNS) == 1
    with dest.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["name"] == "North Valley Hospital"


def test_converters_reject_missing_required_headers(tmp_path: Path):
    import pytest

    bad_ciw = tmp_path / "bad_ciw.csv"
    bad_ciw.write_text("Service URN,Renamed Name\nSIN-1,Home\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing columns"):
        convert_ciw(bad_ciw, tmp_path / "out_ciw.csv")

    bad_cis = tmp_path / "bad_cis.csv"
    bad_cis.write_text(
        "CSNumber,CareService,Subtype,ServiceName,Service_Postcode\n"
        "CS1,Support Service,Care at Home,Home Care,EH1 2NG\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="ServiceStatus"):
        convert_care_inspectorate(bad_cis, tmp_path / "out_cis.csv")

