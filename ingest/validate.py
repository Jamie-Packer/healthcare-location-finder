"""Check raw downloads and marts before a refresh is allowed to publish."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from ingest.registry import SPECS, SourceSpec

LOCATION_MIN_ROWS = 50_000
LOCATION_BAND = 0.10
LAD_MIN_SHARE = 0.90
HEALTH_MIN_SHARE = 0.90
COUNTRY_MIN_ROWS = {
    "England": 76_700,
    "Wales": 2_640,
    "Scotland": 3_760,
    "Northern Ireland": 1_350,
}
SERVICE_TYPES = {"hospital", "care home", "gp", "home care", "other"}
ENTITY_TYPES = {"country", "region", "provider", "site"}


class ValidationError(Exception):
    def __init__(self, failures: list[str]):
        self.failures = failures
        super().__init__("; ".join(failures))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def within_band(rows: int, previous: int | None, band: float, floor: int) -> bool:
    """A small file may move by `floor` rows. A large file may move by `band`."""
    if not previous:
        return True
    return abs(rows - previous) <= max(floor, band * previous)


def _product(spec: SourceSpec) -> tuple[str, bool]:
    if spec.kind == "nspl":
        return "ons/postcodes.parquet", False
    if spec.kind == "cqc":
        return spec.cache[0], True
    return spec.key, spec.header


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
    count = connection.sql(f"select count(*) {query}").fetchall()[0][0]
    connection.close()
    return int(count), columns


def _csv_rows(path: Path) -> tuple[int, list[str]]:
    connection = duckdb.connect()
    relation = connection.sql(
        f"""
        select * from read_csv(
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
    )
    columns = list(relation.columns)
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
    ).fetchall()[0][0]
    connection.close()
    return int(count), columns


def measure_source(raw: Path, spec: SourceSpec) -> int:
    """Row count for one landed file. Raises when the file breaks its contract."""
    relative, header = _product(spec)
    path = raw / relative
    if not path.exists():
        raise ValidationError([f"{relative} is missing"])
    if path.suffix == ".parquet":
        connection = duckdb.connect()
        rows = int(connection.sql(f"select count(*) from read_parquet('{path.as_posix()}')").fetchall()[0][0])
        connection.close()
        columns: list[str] = []
        width = spec.minimum_columns
    elif header:
        rows, columns = _csv_rows(path)
        width = len(columns)
    else:
        rows, width = _ods_shape(path)
        columns = []
    failures: list[str] = []
    if not header and path.suffix != ".parquet" and width < spec.minimum_columns:
        failures.append(f"{relative} has {width} columns, needs {spec.minimum_columns}")
    missing = [name for name in spec.required_columns if name not in columns]
    if missing:
        failures.append(f"{relative} is missing " + ", ".join(missing))
    if rows < spec.minimum_rows:
        failures.append(f"{relative} has {rows} rows, needs {spec.minimum_rows}")
    if failures:
        raise ValidationError(failures)
    return rows


def validate_raw(raw: Path, waived: set[str] | None = None) -> dict[str, int]:
    waived = waived or set()
    failures: list[str] = []
    counts: dict[str, int] = {}
    for spec in SPECS:
        if spec.key in waived:
            continue
        relative, header = _product(spec)
        path = raw / relative
        if not path.exists():
            failures.append(f"{relative} is missing")
            continue
        if path.suffix == ".parquet":
            connection = duckdb.connect()
            rows = int(connection.sql(f"select count(*) from read_parquet('{path.as_posix()}')").fetchall()[0][0])
            connection.close()
            columns: list[str] = []
            width = spec.minimum_columns
        elif header:
            rows, columns = _csv_rows(path)
            width = len(columns)
        else:
            rows, width = _ods_shape(path)
            columns = []
        counts[relative] = rows
        if not header and path.suffix != ".parquet" and width < spec.minimum_columns:
            failures.append(f"{relative} has {width} columns, needs {spec.minimum_columns}")
        missing = [name for name in spec.required_columns if name not in columns]
        if missing:
            failures.append(f"{relative} is missing " + ", ".join(missing))
        if rows < spec.minimum_rows:
            failures.append(f"{relative} has {rows} rows, needs {spec.minimum_rows}")
    if failures:
        raise ValidationError(failures)
    return counts


def validate_marts(
    mart: Path,
    previous: dict | None,
    force: bool,
    waived_countries: set[str] | None = None,
) -> dict[str, int]:
    waived_countries = waived_countries or set()
    location = (mart / "location.parquet").as_posix()
    search = (mart / "search_entity.parquet").as_posix()
    links = (mart / "entity_site.parquet").as_posix()
    connection = duckdb.connect()
    rows, blank_match = connection.sql(
        f"""
        select
            count(*),
            count(*) filter (where match_string is null or trim(match_string) = '')
        from read_parquet('{location}')
        """
    ).fetchall()[0]
    by_country = connection.sql(
        f"""
        select
            country_name,
            count(*),
            count(local_authority_name),
            count(health_area_name)
        from read_parquet('{location}')
        group by 1
        """
    ).fetchall()
    services = {
        service
        for (service,) in connection.sql(
            f"select distinct service_type from read_parquet('{location}')"
        ).fetchall()
    }
    search_count = connection.sql(f"select count(*) from read_parquet('{search}')").fetchall()[0][0]
    entity_types = {
        entity
        for (entity,) in connection.sql(
            f"select distinct entity_type from read_parquet('{search}')"
        ).fetchall()
    }
    link_count = connection.sql(f"select count(*) from read_parquet('{links}')").fetchall()[0][0]
    orphan_links = connection.sql(
        f"""
        select count(*)
        from read_parquet('{links}') as links
        anti join read_parquet('{location}') as location
            on links.location_id = location.location_id
        """
    ).fetchall()[0][0]
    unlinked = connection.sql(
        f"""
        select count(*)
        from read_parquet('{location}') as location
        anti join read_parquet('{links}') as links
            on location.location_id = links.location_id
        """
    ).fetchall()[0][0]
    connection.close()

    failures: list[str] = []
    if rows < LOCATION_MIN_ROWS:
        failures.append(f"location has {rows} rows, needs {LOCATION_MIN_ROWS}")
    if blank_match:
        failures.append(f"{blank_match} locations have an empty match string")
    present = {country: (count, with_lad, with_health) for country, count, with_lad, with_health in by_country}
    unexpected = sorted(name for name in present if name not in COUNTRY_MIN_ROWS)
    if unexpected:
        failures.append("unexpected countries: " + ", ".join(unexpected))
    for country, minimum in COUNTRY_MIN_ROWS.items():
        if country in waived_countries:
            continue
        count, with_lad, with_health = present.get(country, (0, 0, 0))
        if count < minimum:
            failures.append(f"{country} has {count} rows, needs {minimum}")
            continue
        if with_lad / count < LAD_MIN_SHARE:
            failures.append(f"only {with_lad} of {count} {country} locations have a local authority")
        if with_health / count < HEALTH_MIN_SHARE:
            failures.append(f"only {with_health} of {count} {country} locations have a health area")
    missing_services = SERVICE_TYPES - services
    if missing_services:
        failures.append("missing service types: " + ", ".join(sorted(missing_services)))
    missing_entities = ENTITY_TYPES - entity_types
    if missing_entities or search_count < 1_000:
        failures.append(f"search entities look incomplete ({search_count} rows)")
    if orphan_links or unlinked:
        failures.append(f"site links do not match locations ({orphan_links} orphans, {unlinked} unlinked)")

    previous_rows = None
    if previous:
        previous_rows = (previous.get("row_counts") or {}).get("location")
    if previous_rows and not force and not within_band(int(rows), int(previous_rows), LOCATION_BAND, 0):
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
