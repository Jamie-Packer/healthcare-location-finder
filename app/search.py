"""Search current healthcare locations and copy a keyword string."""

from __future__ import annotations

import re
from io import BytesIO

import duckdb
import pandas as pd
import streamlit as st

from data import SAMPLE_WARNING, attribution_markdown, attribution_year, ensure_data

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
EXPORT_COLUMNS = {
    "name": "name",
    "match_string": "match_string",
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
}
# Withhold Excel well below the spreadsheet row limit so a very large extract
# stays a CSV. A full England download is still offered as Excel.
EXCEL_MAX_ROWS = 200_000
LARGE_EXPORT_ROWS = 20_000


def _like(value: str) -> str:
    escaped = re.sub(r"([%_\\])", r"\\\1", value.strip())
    return f"%{escaped}%"


@st.cache_resource
def _connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def _search(search_path: str, query: str) -> pd.DataFrame:
    order = "case entity_type " + " ".join(
        f"when '{entity_type}' then {index}" for index, entity_type in enumerate(TYPE_ORDER)
    ) + " else 99 end"
    return _connection().execute(
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


def _sites(links_path: str, location_path: str, entity_id: str, service_type: str) -> pd.DataFrame:
    service_sql = "" if service_type == "all" else "and location.service_type = ?"
    params: list[str] = [links_path, location_path, entity_id]
    if service_type != "all":
        params.append(service_type)
    columns = ", ".join(f"location.{name}" for name in EXPORT_COLUMNS)
    frame = _connection().execute(
        f"""
        select {columns}
        from read_parquet(?) as links
        inner join read_parquet(?) as location
            on links.location_id = location.location_id
        where links.entity_id = ?
        {service_sql}
        order by location.name
        """,
        params,
    ).df()
    frame = frame.rename(columns=EXPORT_COLUMNS)
    return frame


def _excel(frame: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


def _footer(year: int) -> None:
    st.divider()
    st.markdown(attribution_markdown(year))


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
        if st.button("Help", width="stretch"):
            st.switch_page("help.py")

    if paths.source == "sample":
        st.warning(SAMPLE_WARNING)

    year = attribution_year(paths.manifest)
    query = st.text_input("Location", placeholder="Kent, a trust, a hospital, or a postcode")
    if len(query.strip()) < 2:
        st.info("Type at least two characters.")
        _footer(year)
        return

    hits = _search(paths.search.as_posix(), query)
    if hits.empty:
        st.warning("No matching places.")
        _footer(year)
        return

    labels = []
    for row in hits.itertuples(index=False):
        kind = TYPE_LABELS.get(row.entity_type, row.entity_type)
        code = f" ({row.code})" if row.code and row.code != row.name else ""
        labels.append(f"{kind}: {row.name}{code}")
    choice = st.selectbox("Matching places", options=range(len(labels)), format_func=lambda index: labels[index])
    service = st.selectbox(
        "Service",
        options=["all", "hospital", "care home", "gp", "other"],
        format_func=lambda value: "All" if value == "all" else value.capitalize() if value != "gp" else "GP",
    )
    selected = hits.iloc[int(choice)]
    sites = _sites(paths.links.as_posix(), paths.location.as_posix(), selected.entity_id, service)
    st.write(f"{len(sites):,} current sites")
    if sites.empty:
        _footer(year)
        return

    st.dataframe(sites.head(500), width="stretch", hide_index=True)
    if len(sites) > 500:
        st.caption("Showing the first 500 rows. The download includes every row.")

    keyword_text = "\n".join(sites["match_string"].head(200).astype(str))
    st.text_area("Keyword strings", keyword_text, height=160)
    if len(sites) > 200:
        st.caption("The box has the first 200 keyword strings. The download includes every row.")

    if len(sites) > LARGE_EXPORT_ROWS:
        st.warning(f"{len(sites):,} rows. Preparing a download can take a moment.")
    excel_ok = len(sites) <= EXCEL_MAX_ROWS
    if not excel_ok:
        st.caption("This extract is too large for Excel. Download CSV.")

    token = f"{selected.entity_id}|{service}"
    if st.session_state.get("export_token") != token:
        st.session_state["export_token"] = token
        st.session_state.pop("export_csv", None)
        st.session_state.pop("export_xlsx", None)

    if st.button("Prepare download"):
        st.session_state["export_csv"] = sites.to_csv(index=False).encode("utf-8")
        st.session_state["export_xlsx"] = _excel(sites) if excel_ok else None

    if st.session_state.get("export_csv") and st.session_state.get("export_token") == token:
        left, right = st.columns(2)
        left.download_button(
            "Download CSV",
            st.session_state["export_csv"],
            file_name="locations.csv",
            mime="text/csv",
        )
        if st.session_state.get("export_xlsx"):
            right.download_button(
                "Download Excel",
                st.session_state["export_xlsx"],
                file_name="locations.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    _footer(year)


main()
