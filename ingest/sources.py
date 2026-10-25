"""Find the current public register files.

ODS report URLs stay stable. CQC and the postcode lookup publish a new file
name each release, so those are discovered rather than pinned to a date.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import quote

import requests

ODS = "https://www.odsdatasearchandexport.nhs.uk/api/getReport?report={report}"
ODS_REPORTS = {
    "ods/etr.csv": "etr",
    "ods/ets.csv": "ets",
    "ods/ephp.csv": "ephp",
    "ods/ephpsite.csv": "ephpsite",
    "ods/eother.csv": "eother",
}
CQC_PAGE = "https://www.cqc.org.uk/about-us/transparency/using-cqc-data"
CQC_ACTIVE = "cqc/active_locations.ods"
CQC_DEACTIVATED = "cqc/deactivated_locations.ods"
NSPL_KEY = "ons/nspl.zip"
NSPL_SEARCH = (
    "https://www.arcgis.com/sharing/rest/search?f=json&num=20"
    "&sortField=modified&sortOrder=desc&q="
    + quote('owner:ONSGeography_data AND type:"CSV Collection" AND tags:PRD_NSPL')
)
NSPL_ZIP = re.compile(r"^NSPL_([A-Z]{3})_(\d{4})\.zip$")
MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}
FILE_MONTHS = {name: number for number, name in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"],
    start=1,
)}
CQC_DATED = re.compile(
    r"/(\d{4})-(\d{2})/(\d{2})_([A-Za-z]+)_(\d{4})_(HSCA_Active_Locations|Deactivated_Locations)\.ods",
    re.IGNORECASE,
)
POSTCODE_COLUMNS = {
    "country_code": re.compile(r"^ctry(\d{2})cd$", re.IGNORECASE),
    "region_code": re.compile(r"^rgn(\d{2})cd$", re.IGNORECASE),
    "county_code": re.compile(r"^cty(\d{2})cd$", re.IGNORECASE),
    "local_authority_code": re.compile(r"^lad(\d{2})cd$", re.IGNORECASE),
    "icb_code": re.compile(r"^icb(\d{2})cd$", re.IGNORECASE),
    "sicbl_code": re.compile(r"^sicbl(\d{2})cd$", re.IGNORECASE),
}
NAME_CODE = re.compile(r"^(CTRY|RGN|CTY|LAD|ICB|SICBL)(\d{2})CD$", re.IGNORECASE)
NAME_LABEL = re.compile(r"^(CTRY|RGN|CTY|LAD|ICB|SICBL)(\d{2})NM$", re.IGNORECASE)
NAME_ODS = re.compile(r"^(?:ICB|SICBL)(\d{2})CDH$", re.IGNORECASE)
_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
DATASTORE_SLUG = re.compile(
    r"datastore-(\d{1,2})-([a-z]+)-(\d{4})"
    r"|datastore-(\d{1,2})-(\d{1,2})-(\d{4})"
    r"|datastore-(\d{1,2})([a-z]+)(\d{4})",
    re.IGNORECASE,
)
HREF = re.compile(r'href="([^"]+)"', re.IGNORECASE)


@dataclass
class RemoteFile:
    key: str
    url: str
    publisher_date: str | None = None
    edition: str | None = None
    modified: str | None = None
    last_modified: str | None = None
    etag: str | None = None
    sha256: str | None = None
    size: int | None = None


def discover_ods() -> dict[str, RemoteFile]:
    return {
        key: RemoteFile(key=key, url=ODS.format(report=report))
        for key, report in ODS_REPORTS.items()
    }


def cqc_file_date(url: str) -> date | None:
    match = CQC_DATED.search(html.unescape(url))
    if not match:
        return None
    folder_year, folder_month, day, month_name, year, _kind = match.groups()
    month = FILE_MONTHS.get(month_name.capitalize())
    if month is None or int(folder_year) != int(year) or int(folder_month) != month:
        return None
    return date(int(year), month, int(day))


def cqc_links_from_html(page: str) -> dict[str, RemoteFile]:
    found: dict[str, list[str]] = {CQC_ACTIVE: [], CQC_DEACTIVATED: []}
    for href in HREF.findall(page):
        url = html.unescape(href)
        if url.startswith("/"):
            url = "https://www.cqc.org.uk" + url
        if "HSCA_Active_Locations.ods" in url:
            found[CQC_ACTIVE].append(url)
        elif "Deactivated_Locations.ods" in url:
            found[CQC_DEACTIVATED].append(url)
    chosen: dict[str, RemoteFile] = {}
    for key, urls in found.items():
        dated = [(cqc_file_date(url), url) for url in urls]
        dated = [(stamp, url) for stamp, url in dated if stamp is not None]
        if not dated:
            continue
        stamp, url = max(dated)
        chosen[key] = RemoteFile(
            key=key,
            url=url,
            publisher_date=stamp.isoformat(),
        )
    return chosen


def candidate_cqc_urls(today: date, kind: str) -> list[str]:
    """Dates to try when the data page has no link: the 1st, and the latest week."""
    previous = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    days = {previous, today.replace(day=1), today}
    for offset in range(0, 7):
        days.add(today - timedelta(days=offset))
    urls = []
    for stamp in sorted(days, reverse=True):
        name = f"{stamp.day:02d}_{stamp.strftime('%B')}_{stamp.year}_{kind}.ods"
        urls.append(f"https://www.cqc.org.uk/system/files/{stamp:%Y-%m}/{name}")
    return urls


def _newest_present(session: requests.Session, urls: list[str]) -> str | None:
    found: list[tuple[date, str]] = []
    for url in urls:
        try:
            response = session.head(url, allow_redirects=True, timeout=(15, 30))
        except requests.RequestException:
            continue
        stamp = cqc_file_date(url)
        if response.status_code == 200 and stamp is not None:
            found.append((stamp, url))
    if not found:
        return None
    return max(found)[1]


def discover_cqc(session: requests.Session, today: date | None = None) -> dict[str, RemoteFile]:
    today = today or date.today()
    response = session.get(CQC_PAGE, timeout=(30, 60))
    response.raise_for_status()
    chosen = cqc_links_from_html(response.text)
    probes = {
        CQC_ACTIVE: "HSCA_Active_Locations",
        CQC_DEACTIVATED: "Deactivated_Locations",
    }
    for key, kind in probes.items():
        if key in chosen:
            continue
        url = _newest_present(session, candidate_cqc_urls(today, kind))
        if url is None:
            raise RuntimeError(f"No current CQC file found for {kind}")
        stamp = cqc_file_date(url)
        chosen[key] = RemoteFile(
            key=key,
            url=url,
            publisher_date=stamp.isoformat() if stamp else None,
        )
    for item in chosen.values():
        try:
            head = session.head(item.url, allow_redirects=True, timeout=(15, 30))
        except requests.RequestException:
            continue
        if head.status_code < 400:
            item.last_modified = head.headers.get("Last-Modified")
            item.etag = head.headers.get("ETag")
    return chosen


def nspl_edition(name: str) -> tuple[int, int] | None:
    match = NSPL_ZIP.match(name or "")
    if not match:
        return None
    month = MONTHS.get(match.group(1))
    if month is None:
        return None
    return int(match.group(2)), month


def choose_nspl_item(payload: dict) -> dict:
    best: tuple[tuple[int, int, int], dict] | None = None
    for item in payload.get("results", []):
        edition = nspl_edition(item.get("name") or "")
        if edition is None:
            continue
        rank = (edition[0], edition[1], int(item.get("modified") or 0))
        if best is None or rank > best[0]:
            best = (rank, item)
    if best is None:
        raise RuntimeError("No National Statistics Postcode Lookup zip found")
    return best[1]


def discover_nspl(session: requests.Session) -> RemoteFile:
    response = session.get(NSPL_SEARCH, timeout=(30, 60))
    response.raise_for_status()
    item = choose_nspl_item(response.json())
    name = item["name"]
    edition = name.removesuffix(".zip")
    return RemoteFile(
        key=NSPL_KEY,
        url=f"https://www.arcgis.com/sharing/rest/content/items/{item['id']}/data",
        edition=edition,
        modified=str(item.get("modified") or ""),
        publisher_date=edition,
    )


def discover_sources(session: requests.Session, today: date | None = None) -> dict[str, RemoteFile]:
    found = discover_ods()
    found.update(discover_cqc(session, today))
    found[NSPL_KEY] = discover_nspl(session)
    return found


def identity_unchanged(current: RemoteFile, previous: dict | None) -> bool:
    """CQC and postcode files can be skipped before download. ODS uses a hash."""
    if previous is None or previous.get("url") != current.url:
        return False
    if current.key == NSPL_KEY:
        return previous.get("edition") == current.edition and previous.get("modified") == current.modified
    if current.key in (CQC_ACTIVE, CQC_DEACTIVATED):
        if current.last_modified and previous.get("last_modified"):
            return current.last_modified == previous["last_modified"]
        return True
    return False


def pick_postcode_columns(header: list[str]) -> dict[str, str]:
    """Keep the newest year suffix when a postcode file carries more than one."""
    chosen: dict[str, tuple[int, str]] = {}
    for name in header:
        for key, pattern in POSTCODE_COLUMNS.items():
            match = pattern.match(name.strip())
            if not match:
                continue
            year = int(match.group(1))
            current = chosen.get(key)
            if current is None or year >= current[0]:
                chosen[key] = (year, name.strip())
    missing = [key for key in POSTCODE_COLUMNS if key not in chosen]
    if missing:
        raise RuntimeError("Postcode file is missing " + ", ".join(missing))
    return {key: value[1] for key, value in chosen.items()}


def canonical_name_indexes(header: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, column in enumerate(header):
        label = column.strip()
        if NAME_CODE.match(label):
            mapping["code"] = index
        elif NAME_LABEL.match(label):
            mapping["name"] = index
        elif NAME_ODS.match(label):
            mapping["ods_code"] = index
    if "code" not in mapping or "name" not in mapping:
        raise RuntimeError("Geography name file has no code and name columns")
    return mapping


def choose_ckan_resource(resources: list[dict], pattern: str) -> dict:
    """Pick the newest CSV whose name or URL matches."""
    matched = [
        item for item in resources
        if re.search(pattern, item.get("name") or "", re.IGNORECASE)
        or re.search(pattern, item.get("url") or "", re.IGNORECASE)
    ]
    if not matched:
        raise RuntimeError(f"No catalogue resource matched {pattern}")

    def is_csv(item: dict) -> bool:
        kind = (item.get("format") or "").lower()
        url = (item.get("url") or "").lower()
        return kind == "csv" or url.endswith(".csv")

    pool = [item for item in matched if is_csv(item)] or matched

    def stamp(item: dict) -> str:
        return str(item.get("last_modified") or item.get("created") or "")

    return max(pool, key=stamp)


def ckan_latest(session: requests.Session, base: str, package: str, pattern: str, key: str) -> RemoteFile:
    response = session.get(
        f"{base.rstrip('/')}/api/3/action/package_show",
        params={"id": package},
        timeout=(30, 60),
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"Catalogue lookup failed for {package}")
    chosen = choose_ckan_resource(payload["result"].get("resources") or [], pattern)
    published = str(chosen.get("last_modified") or chosen.get("created") or "")
    return RemoteFile(
        key=key,
        url=chosen["url"],
        publisher_date=published[:10] or None,
        modified=published,
    )


def datastore_date(slug: str) -> date | None:
    """Dates are written three ways on the Care Inspectorate library index."""
    match = DATASTORE_SLUG.search(slug or "")
    if not match:
        return None
    if match.group(1):
        month = _MONTH_NAMES.get(match.group(2).lower())
        if month is None:
            return None
        return date(int(match.group(3)), month, int(match.group(1)))
    if match.group(4):
        return date(int(match.group(6)), int(match.group(5)), int(match.group(4)))
    month = _MONTH_NAMES.get(match.group(8).lower())
    if month is None:
        return None
    return date(int(match.group(9)), month, int(match.group(7)))


def choose_datastore_page(html_text: str) -> tuple[date, str] | None:
    best: tuple[date, str] | None = None
    for href in HREF.findall(html_text):
        url = html.unescape(href)
        stamp = datastore_date(url)
        if stamp is None:
            continue
        if url.startswith("/"):
            url = "https://www.careinspectorate.com" + url
        if best is None or stamp > best[0]:
            best = (stamp, url)
    return best


def csv_link(html_text: str, prefer: str) -> str | None:
    found = [html.unescape(href) for href in HREF.findall(html_text) if href.lower().split("?")[0].endswith(".csv")]
    if not found:
        return None
    preferred = [url for url in found if prefer in url.lower()]
    return (preferred or found)[-1]


def discover_care_inspectorate(session: requests.Session, key: str) -> RemoteFile:
    index = session.get(
        "https://www.careinspectorate.com/index.php/publications-statistics/93-public/datastore",
        timeout=(30, 60),
    )
    index.raise_for_status()
    chosen = choose_datastore_page(index.text)
    if chosen is None:
        raise RuntimeError("No Care Inspectorate datastore page found")
    stamp, page_url = chosen
    page = session.get(page_url, timeout=(30, 60))
    page.raise_for_status()
    url = csv_link(page.text, "datastoreexternal.csv")
    if url is None:
        raise RuntimeError(f"No CSV linked from {page_url}")
    return RemoteFile(key=key, url=url, publisher_date=stamp.isoformat())


def discover_rqia(session: requests.Session, key: str) -> RemoteFile:
    page = session.get("https://www.rqia.org.uk/register/", timeout=(30, 60))
    page.raise_for_status()
    for href in HREF.findall(page.text):
        url = html.unescape(href)
        if "all-registered-services.xlsx" not in url.lower():
            continue
        if url.startswith("/"):
            url = "https://www.rqia.org.uk" + url
        return RemoteFile(key=key, url=url)
    return ckan_latest(
        session,
        "https://admin.opendatani.gov.uk",
        "rqia-regulated-services",
        r"xlsx|registered",
        key,
    )


def discover_ciw(key: str) -> RemoteFile:
    return RemoteFile(
        key=key,
        url="https://digital.careinspectorate.wales/api/DataExport",
    )
