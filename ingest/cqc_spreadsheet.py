"""Stream a CQC spreadsheet into a CSV, dropping person columns."""

from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
WIDTH = 160

ACTIVE_COLUMNS = {
    "cqc_location_id": "Location ID",
    "name": "Location Name",
    "ods_code": "Location ODS Code",
    "postcode": "Location Postal Code",
    "town": "Location City",
    "address_1": "Location Street Address",
    "address_2": "Location Address Line 2",
    "brand_name": "Brand Name",
    "provider_id": "Provider ID",
    "provider_name": "Provider Name",
    "care_home": "Care home?",
    "sector": "Location Type/Sector",
    "primary_category": "Location Primary Inspection Category",
    "region_name": "Location Region",
    "local_authority_name": "Location Local Authority",
    "valid_from": "Location HSCA start date",
    "dormant": "Dormant (Y/N)",
}

DEACTIVATED_COLUMNS = {
    "cqc_location_id": "Location ID",
    "name": "Location Name",
    "ods_code": "Location ODS Code",
    "postcode": "Location Postal Code",
    "valid_from": "Location HSCA start date",
    "valid_to": "Location HSCA End Date",
}


def _cell_text(cell: ET.Element) -> str:
    dated = cell.get(OFFICE + "date-value")
    if dated:
        return dated[:10]
    parts: list[str] = []
    for paragraph in cell.iter(TEXT + "p"):
        if paragraph.text:
            parts.append(paragraph.text)
        for child in list(paragraph):
            if child.tail:
                parts.append(child.tail)
    if parts:
        return "".join(parts).strip()
    return (cell.get(OFFICE + "value") or "").strip()


def _row_values(row: ET.Element) -> list[str]:
    values: list[str] = []
    for cell in row:
        if cell.tag not in (TABLE + "table-cell", TABLE + "covered-table-cell"):
            continue
        text = "" if cell.tag == TABLE + "covered-table-cell" else _cell_text(cell)
        repeat = int(cell.get(TABLE + "number-columns-repeated") or "1")
        room = WIDTH - len(values)
        if room <= 0:
            break
        values.extend([text] * min(repeat, room))
    return values


def _is_location_sheet(header: list[str]) -> bool:
    names = set(header)
    return "Location ID" in names and "Location Name" in names and (
        "Location Postal Code" in names or "Location ODS Code" in names
    )


def convert_locations(source: Path, dest: Path, columns: dict[str, str]) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with zipfile.ZipFile(source) as bundle, bundle.open("content.xml") as handle:
        with dest.open("w", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=list(columns))
            writer.writeheader()
            selected = False
            header_index: dict[str, int] | None = None
            for event, elem in ET.iterparse(handle, events=("start", "end")):
                if event == "start" and elem.tag == TABLE + "table":
                    header_index = None
                    selected = False
                elif event == "end" and elem.tag == TABLE + "table-row":
                    values = _row_values(elem)
                    if header_index is None:
                        if values and _is_location_sheet(values) and written == 0:
                            header_index = {name: index for index, name in enumerate(values)}
                            selected = True
                    elif selected:
                        row = {
                            key: values[header_index[label]].strip()
                            if label in header_index and header_index[label] < len(values)
                            else ""
                            for key, label in columns.items()
                        }
                        if row.get("cqc_location_id"):
                            writer.writerow(row)
                            written += 1
                    elem.clear()
                elif event == "end" and elem.tag == TABLE + "table":
                    elem.clear()
    if written == 0:
        raise RuntimeError(f"No location rows found in {source}")
    return written
