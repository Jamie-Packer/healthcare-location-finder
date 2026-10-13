"""Search current healthcare locations and download a table of sites."""

from __future__ import annotations

import html
import re
from io import BytesIO

import duckdb
import pandas as pd
import streamlit as st

from data import SAMPLE_WARNING, attribution_markdown, attribution_year, ensure_data
from match_text import download_stem, strip_stopwords

TYPE_LABELS = {
    "country": "Country",
    "region": "Region",
    "icb": "Integrated care board",
    "county": "County",
    "local_authority": "Local authority",
    "postcode": "Postcode",
    "provider": "Provider",
    "site": "Site",
}
TYPE_ORDER = list(TYPE_LABELS)
SERVICES = {
    "hospital": "Hospital",
    "care home": "Care home",
    "gp": "GP",
    "other": "Other",
}
EXAMPLES = ("Kent", "East Kent Hospitals", "TN24 0LZ")
EXPORT_COLUMNS = {
    "name": "name",
    "parent_name": "parent_name",
    "postcode": "postcode",
    "town": "town",
    "local_authority_name": "local_authority",
    "region_name": "region",
    "icb_name": "icb",
    "ods_code": "ods_code",
    "cqc_location_id": "cqc_location_id",
    "service_type": "service_type",
    "valid_from": "valid_from",
    "valid_to": "valid_to",
    "match_string": "match_string",
}
# Withhold Excel well below the spreadsheet row limit so a very large extract
# stays a CSV. A full England download is still offered as Excel.
EXCEL_MAX_ROWS = 200_000
LARGE_EXPORT_ROWS = 20_000
TABLE_ROWS = 500

GUIDE = """
1. **Search.** Type a place or a name: a county, a trust, a hospital, a postcode,
   an ODS code or a CQC location id.
2. **Pick a match.** The list can include a region, a county, a local authority,
   an integrated care board, a provider or a single site.
3. **Choose services.** Leave the service filter empty to see every site, or
   pick one or more types.
4. **Download the table.** Prepare a CSV, or an Excel file when the extract is
   small enough. The file has one row per site in your selection.

**Full guide**, top right, covers what is and is not included, and what each column means.
"""


def _like(value: str) -> str:
    escaped = re.sub(r"([%_\\])", r"\\\1", value.strip())
    return f"%{escaped}%"


@st.cache_resource
def _connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


@st.cache_data(show_spinner=False, max_entries=256)
def _search(search_path: str, query: str, stamp: str) -> pd.DataFrame:
    order = "case entity_type " + " ".join(
        f"when '{entity_type}' then {index}" for index, entity_type in enumerate(TYPE_ORDER)
    ) + " else 99 end"
    return _connection().cursor().execute(
        f"""
        select entity_id, entity_type, name, code
        from read_parquet(?)
        where search_text ilike ? escape '\\'
        order by
            case
                when upper(coalesce(code, '')) = upper(?) then 0
                when upper(name) = upper(?) then 1
                when upper(name) like upper(?) || '%' escape '\\' then 2
                else 3
            end,
            {order},
            length(name)
        limit 30
        """,
        [search_path, _like(query), query.strip(), query.strip(), query.strip()],
    ).df()


def _where(services: tuple[str, ...]) -> tuple[str, list[str]]:
    if not services:
        return "", []
    marks = ", ".join("?" for _ in services)
    return f"and location.service_type in ({marks})", list(services)


def _query_sites(
    links_path: str,
    location_path: str,
    entity_id: str,
    services: tuple[str, ...],
    limit: int | None,
) -> pd.DataFrame:
    service_sql, service_params = _where(services)
    columns = ", ".join(f"location.{name}" for name in EXPORT_COLUMNS)
    limit_sql = f"limit {int(limit)}" if limit else ""
    frame = _connection().cursor().execute(
        f"""
        select {columns}
        from read_parquet(?) as links
        inner join read_parquet(?) as location
            on links.location_id = location.location_id
        where links.entity_id = ?
        {service_sql}
        order by location.name
        {limit_sql}
        """,
        [links_path, location_path, entity_id, *service_params],
    ).df()
    frame = frame.rename(columns=EXPORT_COLUMNS)
    if "match_string" in frame.columns:
        frame["match_string"] = frame["match_string"].map(strip_stopwords)
    return frame


@st.cache_data(show_spinner=False, max_entries=256)
def _count(links_path: str, location_path: str, entity_id: str, services: tuple[str, ...], stamp: str) -> int:
    service_sql, service_params = _where(services)
    row = _connection().cursor().execute(
        f"""
        select count(*)
        from read_parquet(?) as links
        inner join read_parquet(?) as location
            on links.location_id = location.location_id
        where links.entity_id = ?
        {service_sql}
        """,
        [links_path, location_path, entity_id, *service_params],
    ).fetchone()
    return int(row[0])


@st.cache_data(show_spinner=False, max_entries=32)
def _preview(
    links_path: str,
    location_path: str,
    entity_id: str,
    services: tuple[str, ...],
    stamp: str,
) -> pd.DataFrame:
    return _query_sites(links_path, location_path, entity_id, services, TABLE_ROWS)


def _excel(frame: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


def _footer(year: int) -> None:
    st.divider()
    st.markdown(attribution_markdown(year))


def _use_example(text: str) -> None:
    st.session_state["query"] = text


def _service_summary(services: tuple[str, ...]) -> str:
    if not services:
        return "all service types"
    return ", ".join(label for name, label in SERVICES.items() if name in services)


def main() -> None:
    try:
        paths = ensure_data()
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

    heading, action = st.columns([6, 1], vertical_alignment="center")
    with heading:
        st.title("Healthcare location reference")
    with action:
        if st.button("Full guide", width="stretch"):
            st.switch_page("help.py")
    st.html('<p class="version">v0.1 · England · current sites</p>')
    st.html(
        '<p class="lede">Find current healthcare sites and download a table of the ones you select.</p>'
    )

    if paths.source == "sample":
        st.warning(SAMPLE_WARNING)

    # Open until the first search, then stay out of the way.
    searching = len(str(st.session_state.get("query", "")).strip()) >= 2
    if searching:
        st.session_state["has_searched"] = True
    with st.expander("How to use", expanded=not st.session_state.get("has_searched", False)):
        st.markdown(GUIDE)

    year = attribution_year(paths.manifest)
    stamp = f"{paths.source}|{paths.manifest.get('built_at', '')}"

    search_column, service_column = st.columns([3, 2], gap="large")
    with search_column:
        query = st.text_input(
            "Location",
            key="query",
            placeholder="Kent, a trust, a hospital, or a postcode",
        )
    with service_column:
        selected_services = st.pills(
            "Service",
            options=list(SERVICES),
            format_func=SERVICES.get,
            selection_mode="multi",
            key="services",
            help="Leave empty to include every service type.",
        )
    services = tuple(sorted(selected_services or []))

    if len(query.strip()) < 2:
        st.caption("Type at least two characters, or try an example.")
        columns = st.columns([1, 2, 1.4, 5])
        for column, example in zip(columns, EXAMPLES):
            column.button(example, on_click=_use_example, args=(example,), key=f"example-{example}")
        _footer(year)
        return

    hits = _search(paths.search.as_posix(), query, stamp)
    if hits.empty:
        st.warning("No matching places. Try a shorter name, a county, or a postcode.")
        _footer(year)
        return

    labels = []
    for row in hits.itertuples(index=False):
        kind = TYPE_LABELS.get(row.entity_type, row.entity_type)
        code = f" ({row.code})" if row.code and row.code != row.name else ""
        labels.append(f"{kind}: {row.name}{code}")
    choice = st.selectbox("Matching places", options=range(len(labels)), format_func=lambda index: labels[index])
    selected = hits.iloc[int(choice)]

    links_path = paths.links.as_posix()
    location_path = paths.location.as_posix()
    total = _count(links_path, location_path, selected.entity_id, services, stamp)
    place = html.escape(str(selected["name"]))
    st.html(
        f'<div class="summary">{total:,} current sites '
        f"<span>in {place} · {html.escape(_service_summary(services))}</span></div>"
    )
    if total == 0:
        st.info("No sites match this place and service. Remove a service filter to widen it.")
        _footer(year)
        return

    sites = _preview(links_path, location_path, selected.entity_id, services, stamp)
    st.dataframe(sites, width="stretch", hide_index=True)
    if total > TABLE_ROWS:
        st.caption(f"Showing the first {TABLE_ROWS} sites. The download includes all {total:,}.")

    st.caption("Download one row per site, for every site in this filter.")
    if total > LARGE_EXPORT_ROWS:
        st.warning(f"{total:,} rows. Preparing a download can take a moment.")
    excel_ok = total <= EXCEL_MAX_ROWS
    if not excel_ok:
        st.caption("This extract is too large for Excel. Download CSV.")

    token = f"{selected.entity_id}|{','.join(services)}"
    if st.session_state.get("export_token") != token:
        st.session_state["export_token"] = token
        st.session_state.pop("export_csv", None)
        st.session_state.pop("export_xlsx", None)
        st.session_state.pop("export_stem", None)

    file_stem = download_stem(selected["name"])
    if st.button("Prepare download"):
        with st.spinner("Preparing your files..."):
            everything = _query_sites(links_path, location_path, selected.entity_id, services, None)
            st.session_state["export_csv"] = everything.to_csv(index=False).encode("utf-8")
            st.session_state["export_xlsx"] = _excel(everything) if excel_ok else None
            st.session_state["export_stem"] = file_stem

    if st.session_state.get("export_csv") and st.session_state.get("export_token") == token:
        stem = st.session_state.get("export_stem") or file_stem
        left, right = st.columns(2)
        left.download_button(
            "Download CSV",
            st.session_state["export_csv"],
            file_name=f"{stem}.csv",
            mime="text/csv",
        )
        if st.session_state.get("export_xlsx"):
            right.download_button(
                "Download Excel",
                st.session_state["export_xlsx"],
                file_name=f"{stem}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    _footer(year)


main()
