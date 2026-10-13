"""Check raw downloads and marts before a refresh is allowed to publish."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

ODS_MIN_COLUMNS = {
    "ods/etr.csv": 12,
    "ods/ets.csv": 15,
    "ods/ephp.csv": 12,
    "ods/ephpsite.csv": 15,
    "ods/eother.csv": 12,
}
RAW_MIN_ROWS = {
    "ods/etr.csv": 100,
    "ods/ets.csv": 1_000,
    "ods/ephp.csv": 100,
    "ods/ephpsite.csv": 500,
    "ods/eother.csv": 40,
    "cqc/locations.csv": 30_000,
    "cqc/deactivated_locations.csv": 5_000,
    "ons/postcodes.parquet": 1_000_000,
}
LOCATION_MIN_ROWS = 50_000
LOCATION_BAND = 0.10
LAD_MIN_SHARE = 0.90
SERVICE_TYPES = {"hospital", "care home", "gp", "other"}
ENTITY_TYPES = {"country", "region", "provider", "site"}


class ValidationError(Exception):
    def __init__(self, failures: list[str]):
        self.failures = failures
        super().__init__("; ".join(failures))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _ods_shape(path: Path) -> tuple[int, int]:
    query = f"""
        from read_csv(
            '{path.as_posix()}',
            header = false,
            all_varchar = true,
            quote = '"',
            delim = ',',
            strict_mode = false,
            null_padding = true,
            parallel = false,
            max_line_size = 1048576
        )
    """
    connection = duckdb.connect()
    columns = len(connection.sql(f"select * {query} limit 0").columns)
    count = connection.sql(f"select count(*) {query}").fetchone()[0]
    connection.close()
    return int(count), columns


def _csv_rows(path: Path) -> int:
    connection = duckdb.connect()
    count = connection.sql(
        f"""
        select count(*) from read_csv(
            '{path.as_posix()}',
            header = true,
            all_varchar = true,
            strict_mode = false,
            null_padding = true,
            parallel = false,
            max_line_size = 2000000,
            ignore_errors = true
        )
        """
    ).fetchone()[0]
    connection.close()
    return int(count)


def validate_raw(raw: Path) -> dict[str, int]:
    failures: list[str] = []
    counts: dict[str, int] = {}
    for relative, minimum_columns in ODS_MIN_COLUMNS.items():
        path = raw / relative
        if not path.exists():
            failures.append(f"{relative} is missing")
            continue
        rows, columns = _ods_shape(path)
        counts[relative] = rows
        if columns < minimum_columns:
            failures.append(f"{relative} has {columns} columns, needs {minimum_columns}")
        if rows < RAW_MIN_ROWS[relative]:
            failures.append(f"{relative} has {rows} rows, needs {RAW_MIN_ROWS[relative]}")
    for relative, minimum in RAW_MIN_ROWS.items():
        if relative in ODS_MIN_COLUMNS:
            continue
        path = raw / relative
        if not path.exists():
            failures.append(f"{relative} is missing")
            continue
        if path.suffix == ".parquet":
            connection = duckdb.connect()
            rows = int(connection.sql(f"select count(*) from read_parquet('{path.as_posix()}')").fetchone()[0])
            connection.close()
        else:
            rows = _csv_rows(path)
        counts[relative] = rows
        if rows < minimum:
            failures.append(f"{relative} has {rows} rows, needs {minimum}")
    if failures:
        raise ValidationError(failures)
    return counts


def validate_marts(mart: Path, previous: dict | None, force: bool) -> dict[str, int]:
    location = (mart / "location.parquet").as_posix()
    search = (mart / "search_entity.parquet").as_posix()
    links = (mart / "entity_site.parquet").as_posix()
    connection = duckdb.connect()
    rows, with_lad, blank_match, non_england = connection.sql(
        f"""
        select
            count(*),
            count(local_authority_name),
            count(*) filter (where match_string is null or trim(match_string) = ''),
            count(*) filter (where country_name is distinct from 'England')
        from read_parquet('{location}')
        """
    ).fetchone()
    services = {
        service
        for (service,) in connection.sql(
            f"select distinct service_type from read_parquet('{location}')"
        ).fetchall()
    }
    search_count = connection.sql(f"select count(*) from read_parquet('{search}')").fetchone()[0]
    entity_types = {
        entity
        for (entity,) in connection.sql(
            f"select distinct entity_type from read_parquet('{search}')"
        ).fetchall()
    }
    link_count = connection.sql(f"select count(*) from read_parquet('{links}')").fetchone()[0]
    orphan_links = connection.sql(
        f"""
        select count(*)
        from read_parquet('{links}') as links
        anti join read_parquet('{location}') as location
            on links.location_id = location.location_id
        """
    ).fetchone()[0]
    unlinked = connection.sql(
        f"""
        select count(*)
        from read_parquet('{location}') as location
        anti join read_parquet('{links}') as links
            on location.location_id = links.location_id
        """
    ).fetchone()[0]
    connection.close()

    failures: list[str] = []
    if rows < LOCATION_MIN_ROWS:
        failures.append(f"location has {rows} rows, needs {LOCATION_MIN_ROWS}")
    if blank_match:
        failures.append(f"{blank_match} locations have an empty match string")
    if non_england:
        failures.append(f"{non_england} locations are not England")
    missing_services = SERVICE_TYPES - services
    if missing_services:
        failures.append("missing service types: " + ", ".join(sorted(missing_services)))
    if rows and with_lad / rows < LAD_MIN_SHARE:
        failures.append(f"only {with_lad} of {rows} locations have a local authority")
    missing_entities = ENTITY_TYPES - entity_types
    if missing_entities or search_count < 1_000:
        failures.append(f"search entities look incomplete ({search_count} rows)")
    if orphan_links or unlinked:
        failures.append(f"site links do not match locations ({orphan_links} orphans, {unlinked} unlinked)")

    previous_rows = None
    if previous:
        previous_rows = (previous.get("row_counts") or {}).get("location")
    if previous_rows and not force:
        change = abs(rows - previous_rows) / previous_rows
        if change > LOCATION_BAND:
            failures.append(
                f"location rows moved from {previous_rows} to {rows}, "
                f"outside {LOCATION_BAND:.0%}"
            )
    if failures:
        raise ValidationError(failures)
    return {
        "location": int(rows),
        "search_entity": int(search_count),
        "entity_site": int(link_count),
    }
