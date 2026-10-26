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
    "United Kingdom": _flag_uri("united-kingdom.svg"),
    "England": _flag_uri("england.svg"),
    "Scotland": _flag_uri("scotland.svg"),
    "Wales": _flag_uri("wales.svg"),
}
COUNTRY_CHOICES = ("United Kingdom", "England", "Scotland", "Wales", "Northern Ireland")
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
1. **Country or search.** Choose a country to list its sites, or the United Kingdom
   to list every site. Or type a place: a county, a trust, a hospital, a postcode,
   an NHS code or a regulator id.
2. **Pick a place.** If you searched, choose a result. A result can be a country,
   a health board, an integrated care board, an HSC trust area, a provider or a
   single site.
3. **Narrow it down.** Pick services, or leave them empty to keep everything.
   A chosen country also narrows a place you searched. **Columns** changes what
   the table shows.
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


def _filters(services: tuple[str, ...], countries: tuple[str, ...]) -> tuple[str, list[str]]:
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
    return " and ".join(clauses), params


def _query_sites(
    links_path: str,
    location_path: str,
    entity_id: str | None,
    services: tuple[str, ...],
    countries: tuple[str, ...],
    columns: tuple[str, ...],
    limit: int | None,
) -> pd.DataFrame:
    filter_sql, filter_params = _filters(services, countries)
    selected = ", ".join(f"location.{name}" for name in columns)
    limit_sql = f"limit {int(limit)}" if limit else ""
    if entity_id is None:
        where_sql = f"where {filter_sql}" if filter_sql else ""
        frame = _connection().cursor().execute(
            f"""
            select {selected}
            from read_parquet(?) as location
            {where_sql}
            order by location.name
            {limit_sql}
            """,
            [location_path, *filter_params],
        ).df()
    else:
        where_sql = f"and {filter_sql}" if filter_sql else ""
        frame = _connection().cursor().execute(
            f"""
            select {selected}
            from read_parquet(?) as links
            inner join read_parquet(?) as location
                on links.location_id = location.location_id
            where links.entity_id = ?
            {where_sql}
            order by location.name
            {limit_sql}
            """,
            [links_path, location_path, entity_id, *filter_params],
        ).df()
    frame = frame.rename(columns=COLUMN_LABELS)
    if "match_string" in frame.columns:
        frame["match_string"] = frame["match_string"].map(strip_stopwords)
    return frame


@st.cache_data(show_spinner=False, max_entries=256)
def _count(
    links_path: str,
    location_path: str,
    entity_id: str | None,
    services: tuple[str, ...],
    countries: tuple[str, ...],
    stamp: str,
) -> int:
    filter_sql, filter_params = _filters(services, countries)
    if entity_id is None:
        where_sql = f"where {filter_sql}" if filter_sql else ""
        row = _connection().cursor().execute(
            f"""
            select count(*)
            from read_parquet(?) as location
            {where_sql}
            """,
            [location_path, *filter_params],
        ).fetchone()
    else:
        where_sql = f"and {filter_sql}" if filter_sql else ""
        row = _connection().cursor().execute(
            f"""
            select count(*)
            from read_parquet(?) as links
            inner join read_parquet(?) as location
                on links.location_id = location.location_id
            where links.entity_id = ?
            {where_sql}
            """,
            [links_path, location_path, entity_id, *filter_params],
        ).fetchone()
    return int(row[0])


@st.cache_data(show_spinner=False, max_entries=32)
def _preview(
    links_path: str,
    location_path: str,
    entity_id: str | None,
    services: tuple[str, ...],
    countries: tuple[str, ...],
    columns: tuple[str, ...],
    stamp: str,
) -> pd.DataFrame:
    body = [name for name in columns if name != "match_string"]
    frame = _query_sites(
        links_path,
        location_path,
        entity_id,
        services,
        countries,
        tuple(body + ["match_string"]),
        TABLE_ROWS,
    )
    text = [name for name in frame.columns if pd.api.types.is_string_dtype(frame[name])]
    frame[text] = frame[text].fillna("")
    return frame


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


def _country_slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def _flag_rules() -> str:
    rules = []
    for name, uri in FLAGS.items():
        rules.append(
            f'[class*="st-key-country-option-{_country_slug(name)}"] button {{'
            f'background-image: url("{uri}");}}'
        )
    return " ".join(rules)


def _country_dropdown() -> str | None:
    selected = st.session_state.get("country")
    if selected not in COUNTRY_CHOICES:
        selected = None
    flag = FLAGS.get(selected or "")
    trigger = (
        f'background-image: url("{flag}"); padding-left: 2.55rem;'
        if flag
        else "padding-left: 0.85rem;"
    )
    st.html(
        '<p class="country-label">Country</p>'
        "<style>"
        f"[class*='st-key-country-menu'] [data-testid='stPopoverButton'] {{ {trigger} }}"
        "[class*='st-key-country-menu'] [data-testid='stPopoverButton'] > div > div:first-child"
        "{ justify-content: flex-start !important; }"
        f"{_flag_rules()}"
        "</style>"
    )
    label = selected or "Select a country"
    menu_key = f"country-menu-{_country_slug(selected) if selected else 'none'}"
    with st.popover(label, key=menu_key, width="stretch"):
        for name in COUNTRY_CHOICES:
            if st.button(name, key=f"country-option-{_country_slug(name)}", width="stretch"):
                st.session_state["country"] = name
                st.rerun()
        if selected is not None and st.button("Clear country", key="country-clear", width="stretch"):
            st.session_state["country"] = None
            st.rerun()
    return selected


def _summary(total: int, place: str, services: tuple[str, ...], countries: tuple[str, ...], nationwide: bool) -> str:
    detail = _service_summary(services)
    if not nationwide:
        detail = f"{detail} · {_country_summary(countries)}"
    return (
        f'<div class="summary">{total:,} current sites '
        f"<span>in {html.escape(place)} · {html.escape(detail)}</span></div>"
    )


def _show_place(
    links_path: str,
    location_path: str,
    entity_id: str | None,
    services: tuple[str, ...],
    countries: tuple[str, ...],
    columns: tuple[str, ...],
    place: str,
    file_label: str,
    year: int,
    stamp: str,
    nationwide: bool,
) -> None:
    total = _count(links_path, location_path, entity_id, services, countries, stamp)
    st.html(_summary(total, place, services, countries, nationwide))
    if total == 0:
        st.info("No sites for this place and filter. Change the country or the service to widen it.")
        _footer(year)
        return

    sites = _preview(links_path, location_path, entity_id, services, countries, columns, stamp)
    st.dataframe(sites, width="stretch", hide_index=True)
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

    identity = entity_id or "all"
    token = f"{identity}|{','.join(services)}|{','.join(countries)}|{','.join(columns)}"
    if st.session_state.get("export_token") != token:
        st.session_state["export_token"] = token
        st.session_state.pop("export_csv", None)
        st.session_state.pop("export_xlsx", None)
        st.session_state.pop("export_stem", None)

    file_stem = download_stem(file_label)
    with st.container(horizontal=True):
        if st.button("Prepare download", type="primary"):
            with st.spinner("Preparing your files..."):
                everything = _query_sites(
                    links_path, location_path, entity_id, services, countries, columns, None
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
    st.html('<p class="version">v0.2.1 · UK · current sites</p>')
    st.html(
        '<p class="lede">Find current healthcare sites and download a table of the ones you select.</p>'
    )

    if paths.source == "sample":
        st.warning(SAMPLE_WARNING)

    # Open until the first search or country choice, then stay out of the way.
    searching = (
        len(str(st.session_state.get("query", "")).strip()) >= 2
        or st.session_state.get("country") in COUNTRY_CHOICES
    )
    if searching:
        st.session_state["has_searched"] = True
    with st.expander("How to use", expanded=not st.session_state.get("has_searched", False)):
        st.markdown(GUIDE)

    year = attribution_year(paths.manifest)
    stamp = f"{paths.source}|{paths.manifest.get('built_at', '')}"

    search_column, column_column = st.columns([5, 1], vertical_alignment="bottom")
    with search_column:
        query = st.text_input(
            "Search",
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
        country = _country_dropdown()
    services = tuple(sorted(selected_services or []))
    countries = () if country in (None, "United Kingdom") else (country,)
    columns = chosen_columns(selected_column_names)
    links_path = paths.links.as_posix()
    location_path = paths.location.as_posix()

    if len(query.strip()) < 2:
        if country is None:
            st.caption("Type at least two characters, choose a country, or try an example.")
            with st.container(horizontal=True):
                for example in EXAMPLES:
                    st.button(example, on_click=_use_example, args=(example,), key=f"example-{example}")
            _footer(year)
            return
        place = "the United Kingdom" if country == "United Kingdom" else country
        _show_place(
            links_path,
            location_path,
            None if country == "United Kingdom" else f"country:{country}",
            services,
            (),
            columns,
            place,
            "United Kingdom" if country == "United Kingdom" else country,
            year,
            stamp,
            True,
        )
        return

    hits = _search(paths.search.as_posix(), query, stamp)
    if hits.empty:
        st.warning("No places found. Try a shorter name, a county, or a postcode.")
        _footer(year)
        return

    labels = []
    for row in hits.itertuples(index=False):
        kind = TYPE_LABELS.get(row.entity_type, row.entity_type)
        code = f" ({row.code})" if row.code and row.code != row.name else ""
        labels.append(f"{kind}: {row.name}{code}")
    choice = st.selectbox("Places", options=range(len(labels)), format_func=lambda index: labels[index])
    selected = hits.iloc[int(choice)]
    _show_place(
        links_path,
        location_path,
        str(selected.entity_id),
        services,
        countries,
        columns,
        str(selected["name"]),
        str(selected["name"]),
        year,
        stamp,
        False,
    )


main()
