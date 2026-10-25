"""Search current healthcare locations and download a table of sites."""

from __future__ import annotations

import base64
import html
import re
from io import BytesIO
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from data import SAMPLE_WARNING, attribution_markdown, attribution_year, ensure_data
from match_text import ALL_COLUMNS, DEFAULT_COLUMNS, chosen_columns, download_stem, strip_stopwords


def _flag_uri(name: str) -> str:
    path = Path(__file__).resolve().parent / "assets" / "flags" / name
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{payload}"


FLAGS = {
    "England": _flag_uri("england.svg"),
    "Scotland": _flag_uri("scotland.svg"),
    "Wales": _flag_uri("wales.svg"),
    "Northern Ireland": _flag_uri("united-kingdom.svg"),
}
TYPE_LABELS = {
    "country": "Country",
    "region": "Region",
    "health_board": "Health board",
    "hsc_trust": "HSC trust area",
    "icb": "Integrated care board",
    "county": "County",
    "local_authority": "Local authority",
    "postcode": "Postcode",
    "provider": "Provider",
    "site": "Site",
}
TYPE_ORDER = list(TYPE_LABELS)
COUNTRIES = ("England", "Wales", "Scotland", "Northern Ireland")
SERVICES = {
    "hospital": "Hospital",
    "care home": "Care home",
    "gp": "GP",
    "home care": "Home care",
    "other": "Other",
}
EXAMPLES = ("Kent", "NHS Lothian", "Cardiff", "Belfast")
COLUMN_LABELS = {
    "name": "name",
    "parent_name": "parent_name",
    "address": "address",
    "town": "town",
    "postcode": "postcode",
    "postcode_compact": "postcode_compact",
    "country_name": "country",
    "local_authority_name": "local_authority",
    "local_authority_code": "local_authority_code",
    "county_name": "county",
    "county_code": "county_code",
    "region_name": "region",
    "region_code": "region_code",
    "health_area_name": "health_area",
    "health_area_type": "health_area_type",
    "health_area_code": "health_area_code",
    "health_area_ods_code": "health_area_ods_code",
    "parent_code": "parent_code",
    "nhs_code": "nhs_code",
    "regulator": "regulator",
    "regulator_id": "regulator_id",
    "service_type": "service_type",
    "source": "source",
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
   an NHS code or a regulator id.
2. **Pick a match.** A match can be a country, a health board, an integrated care
   board, an HSC trust area, a provider or a single site.
3. **Narrow it down.** Pick services and countries, or leave them empty to keep
   everything. **Columns** changes what the table shows.
4. **Download.** Prepare a CSV, or an Excel file when the extract is small enough.
   It has one row per site, with the columns you chose.

**Full guide**, top right, covers what is included and what each column means.
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


def _where(services: tuple[str, ...], countries: tuple[str, ...]) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []
    if services:
        marks = ", ".join("?" for _ in services)
        clauses.append(f"location.service_type in ({marks})")
        params.extend(services)
    if countries:
        marks = ", ".join("?" for _ in countries)
        clauses.append(f"location.country_name in ({marks})")
        params.extend(countries)
    if not clauses:
        return "", []
    return "and " + " and ".join(clauses), params


def _query_sites(
    links_path: str,
    location_path: str,
    entity_id: str,
    services: tuple[str, ...],
    countries: tuple[str, ...],
    columns: tuple[str, ...],
    limit: int | None,
) -> pd.DataFrame:
    filter_sql, filter_params = _where(services, countries)
    selected = ", ".join(f"location.{name}" for name in columns)
    limit_sql = f"limit {int(limit)}" if limit else ""
    frame = _connection().cursor().execute(
        f"""
        select {selected}
        from read_parquet(?) as links
        inner join read_parquet(?) as location
            on links.location_id = location.location_id
        where links.entity_id = ?
        {filter_sql}
        order by location.name
        {limit_sql}
        """,
        [links_path, location_path, entity_id, *filter_params],
    ).df()
    frame = frame.rename(columns=COLUMN_LABELS)
    if "match_string" in frame.columns:
        frame["match_string"] = frame["match_string"].map(strip_stopwords)
    return frame


def _with_flags(frame: pd.DataFrame) -> pd.DataFrame:
    if "country" not in frame.columns:
        return frame
    shown = frame.copy()
    shown.insert(
        0,
        "flag",
        shown["country"].map(lambda name: FLAGS.get(name)),
    )
    return shown


@st.cache_data(show_spinner=False, max_entries=256)
def _count(
    links_path: str,
    location_path: str,
    entity_id: str,
    services: tuple[str, ...],
    countries: tuple[str, ...],
    stamp: str,
) -> int:
    filter_sql, filter_params = _where(services, countries)
    row = _connection().cursor().execute(
        f"""
        select count(*)
        from read_parquet(?) as links
        inner join read_parquet(?) as location
            on links.location_id = location.location_id
        where links.entity_id = ?
        {filter_sql}
        """,
        [links_path, location_path, entity_id, *filter_params],
    ).fetchone()
    return int(row[0])


@st.cache_data(show_spinner=False, max_entries=32)
def _preview(
    links_path: str,
    location_path: str,
    entity_id: str,
    services: tuple[str, ...],
    countries: tuple[str, ...],
    columns: tuple[str, ...],
    stamp: str,
) -> pd.DataFrame:
    body = [name for name in columns if name != "match_string"]
    if "country_name" not in body:
        body.append("country_name")
    frame = _query_sites(
        links_path,
        location_path,
        entity_id,
        services,
        countries,
        tuple(body + ["match_string"]),
        TABLE_ROWS,
    )
    shown = _with_flags(frame)
    if "country_name" not in columns and "country" in shown.columns:
        shown = shown.drop(columns=["country"])
    text = [name for name in shown.columns if name != "flag" and pd.api.types.is_string_dtype(shown[name])]
    shown[text] = shown[text].fillna("")
    return shown


def _excel(frame: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


def _footer(year: int) -> None:
    st.divider()
    st.markdown(attribution_markdown(year))


def _use_example(text: str) -> None:
    st.session_state["query"] = text


def _reset_columns() -> None:
    st.session_state["columns"] = list(DEFAULT_COLUMNS)


def _service_summary(services: tuple[str, ...]) -> str:
    if not services:
        return "all service types"
    return ", ".join(label for name, label in SERVICES.items() if name in services)


def _country_summary(countries: tuple[str, ...]) -> str:
    if not countries:
        return "all countries"
    return ", ".join(countries)


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
    st.html('<p class="version">v0.2 · UK · current sites</p>')
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

    search_column, column_column = st.columns([5, 1], vertical_alignment="bottom")
    with search_column:
        query = st.text_input(
            "Location",
            key="query",
            placeholder="Kent, NHS Lothian, Cardiff, or a postcode",
        )
    st.session_state.setdefault("columns", list(DEFAULT_COLUMNS))
    with column_column:
        with st.popover("Columns", icon=":material/view_column:", width="stretch"):
            selected_column_names = st.multiselect(
                "Table and download columns",
                options=list(ALL_COLUMNS),
                format_func=COLUMN_LABELS.get,
                key="columns",
            )
            st.caption("The keyword string, `match_string`, always comes last.")
            st.button("Default columns", on_click=_reset_columns, width="stretch")
    service_column, country_column = st.columns(2, gap="medium")
    with service_column:
        selected_services = st.pills(
            "Service",
            options=list(SERVICES),
            format_func=SERVICES.get,
            selection_mode="multi",
            key="services",
            help="Leave empty to include every service type.",
        )
    with country_column:
        selected_countries = st.pills(
            "Country",
            options=list(COUNTRIES),
            selection_mode="multi",
            key="countries",
            help="Leave empty to include every UK country.",
        )
    services = tuple(sorted(selected_services or []))
    countries = tuple(selected_countries or [])
    columns = chosen_columns(selected_column_names)

    if len(query.strip()) < 2:
        st.caption("Type at least two characters, or try an example.")
        with st.container(horizontal=True):
            for example in EXAMPLES:
                st.button(example, on_click=_use_example, args=(example,), key=f"example-{example}")
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
    total = _count(links_path, location_path, selected.entity_id, services, countries, stamp)
    place = html.escape(str(selected["name"]))
    st.html(
        f'<div class="summary">{total:,} current sites '
        f"<span>in {place} · {html.escape(_service_summary(services))} · "
        f"{html.escape(_country_summary(countries))}</span></div>"
    )
    if total == 0:
        st.info("No sites match this place and filter. Clear a country or service to widen it.")
        _footer(year)
        return

    sites = _preview(
        links_path, location_path, selected.entity_id, services, countries, columns, stamp
    )
    st.dataframe(
        sites,
        width="stretch",
        hide_index=True,
        column_config={
            "flag": st.column_config.ImageColumn(" ", help="Country", width="small"),
        },
    )
    excel_ok = total <= EXCEL_MAX_ROWS
    if total > TABLE_ROWS:
        note = f"Showing the first {TABLE_ROWS} sites. The download has all {total:,}, one row per site."
    else:
        note = "The download has one row for every site in this filter."
    if not excel_ok:
        note += " It is too large for Excel, so it comes as CSV only."
    elif total > LARGE_EXPORT_ROWS:
        note += f" Preparing {total:,} rows can take a moment."
    st.caption(note)

    token = f"{selected.entity_id}|{','.join(services)}|{','.join(countries)}|{','.join(columns)}"
    if st.session_state.get("export_token") != token:
        st.session_state["export_token"] = token
        st.session_state.pop("export_csv", None)
        st.session_state.pop("export_xlsx", None)
        st.session_state.pop("export_stem", None)

    file_stem = download_stem(selected["name"])
    with st.container(horizontal=True):
        if st.button("Prepare download", type="primary"):
            with st.spinner("Preparing your files..."):
                everything = _query_sites(
                    links_path, location_path, selected.entity_id, services, countries, columns, None
                )
                st.session_state["export_csv"] = everything.to_csv(index=False).encode("utf-8")
                st.session_state["export_xlsx"] = _excel(everything) if excel_ok else None
                st.session_state["export_stem"] = file_stem

        if st.session_state.get("export_csv") and st.session_state.get("export_token") == token:
            stem = st.session_state.get("export_stem") or file_stem
            st.download_button(
                "Download CSV",
                st.session_state["export_csv"],
                file_name=f"{stem}.csv",
                mime="text/csv",
                icon=":material/download:",
            )
            if st.session_state.get("export_xlsx"):
                st.download_button(
                    "Download Excel",
                    st.session_state["export_xlsx"],
                    file_name=f"{stem}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    icon=":material/download:",
                )

    _footer(year)


main()
