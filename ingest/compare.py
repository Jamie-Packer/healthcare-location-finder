"""Compare a new mart with the previous published release.

A rename keeps the same id. A removal is reported and nothing is deleted from
the previous release. An identifier that points at more than one site is left
unresolved, one row per site, rather than matched to the first row. A site whose
key changed is a transition only: it is not also an added site and a removed site.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from ingest.contract import ENTITY_CHANGES, IDENTITY_CHANGES

_NATIVE = """
select
    substr(entity_id, 6) as location_id,
    identifier_system,
    identifier_value
from read_parquet('{path}')
where entity_id like 'site:%'
    and identifier_value is not null
"""

_PROJECTED = """
select
    substr(entity_id, 6) as location_id,
    case identifier_system
        when 'ods' then 'nhs_code'
        when 'phs_hospital' then 'nhs_code'
        when 'phs_practice' then 'nhs_code'
        when 'cqc_location' then 'regulator:CQC'
        when 'ciw_service' then 'regulator:CIW'
        when 'care_inspectorate_service' then 'regulator:Care Inspectorate'
        when 'rqia_service' then 'regulator:RQIA'
        else identifier_system
    end as identifier_system,
    identifier_value
from read_parquet('{path}')
where entity_id like 'site:%'
    and identifier_value is not null
"""

_LEGACY = """
select location_id, 'nhs_code' as identifier_system, nhs_code as identifier_value
from read_parquet('{path}')
where nhs_code is not null and nhs_code <> ''
union all
select location_id, 'regulator:' || coalesce(regulator, ''), regulator_id
from read_parquet('{path}')
where regulator_id is not null and regulator_id <> ''
"""


def _empty(path: Path, header: tuple[str, ...]) -> None:
    path.write_text(",".join(header) + "\n", encoding="utf-8", newline="\n")


def _previous_build(previous: Path) -> str | None:
    manifest = previous / "manifest.json"
    if not manifest.exists():
        return None
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return payload.get("build_id") or payload.get("built_at")


def _identifier_sql(directory: Path, legacy: bool) -> str:
    identifier = directory / "entity_identifier.parquet"
    if identifier.exists():
        template = _PROJECTED if legacy else _NATIVE
        return template.format(path=identifier.as_posix())
    return _LEGACY.format(path=(directory / "location.parquet").as_posix())


def write_comparison(current: Path, previous: Path | None, dest: Path) -> dict:
    """Write the two change files and return the summary stored in the manifest."""
    dest.mkdir(parents=True, exist_ok=True)
    identity_path = dest / IDENTITY_CHANGES.filename
    entity_path = dest / ENTITY_CHANGES.filename
    if previous is None or not (previous / "location.parquet").exists():
        _empty(identity_path, tuple(column.name for column in IDENTITY_CHANGES.columns))
        _empty(entity_path, tuple(column.name for column in ENTITY_CHANGES.columns))
        summary = {
            "performed": False,
            "reason": "no previous release",
            "previous_build_id": None,
        }
        (dest / "release_diff.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary

    legacy = not (previous / "entity_identifier.parquet").exists()
    current_ids = _identifier_sql(current, legacy)
    previous_ids = _identifier_sql(previous, False)
    current_location = (current / "location.parquet").as_posix()
    previous_location = (previous / "location.parquet").as_posix()
    current_entity = (current / "search_entity.parquet").as_posix()
    previous_entity = (previous / "search_entity.parquet").as_posix()
    current_link = (current / "entity_site.parquet").as_posix()
    previous_link = (previous / "entity_site.parquet").as_posix()
    connection = duckdb.connect()
    try:
        connection.execute(
            f"""
            create temporary table current_ids as
            select distinct location_id, identifier_system, identifier_value
            from ({current_ids}) as ids
            where location_id is not null and identifier_system is not null
            """
        )
        connection.execute(
            f"""
            create temporary table previous_ids as
            select distinct location_id, identifier_system, identifier_value
            from ({previous_ids}) as ids
            where location_id is not null and identifier_system is not null
            """
        )
        connection.execute(
            """
            create temporary table identity_changes as
            with counts as (
                select
                    identifier_system,
                    identifier_value,
                    count(distinct location_id) filter (where side = 'previous') as previous_count,
                    count(distinct location_id) filter (where side = 'current') as current_count
                from (
                    select 'previous' as side, location_id, identifier_system, identifier_value from previous_ids
                    union all
                    select 'current', location_id, identifier_system, identifier_value from current_ids
                ) as sides
                group by 1, 2
            ),
            ambiguous as (
                select identifier_system, identifier_value
                from counts
                where previous_count > 1 or current_count > 1
            )
            select
                'unresolved' as change,
                ids.identifier_system,
                ids.identifier_value,
                case when ids.side = 'previous' then ids.location_id end as previous_location_id,
                case when ids.side = 'current' then ids.location_id end as location_id
            from (
                select 'previous' as side, location_id, identifier_system, identifier_value from previous_ids
                union all
                select 'current', location_id, identifier_system, identifier_value from current_ids
            ) as ids
            inner join ambiguous
                on ambiguous.identifier_system = ids.identifier_system
                and ambiguous.identifier_value = ids.identifier_value
            union all
            select
                'transition',
                previous_ids.identifier_system,
                previous_ids.identifier_value,
                previous_ids.location_id,
                current_ids.location_id
            from previous_ids
            inner join current_ids
                on current_ids.identifier_system = previous_ids.identifier_system
                and current_ids.identifier_value = previous_ids.identifier_value
            inner join counts
                on counts.identifier_system = previous_ids.identifier_system
                and counts.identifier_value = previous_ids.identifier_value
            where counts.previous_count = 1
                and counts.current_count = 1
                and previous_ids.location_id <> current_ids.location_id
            """
        )
        connection.execute(
            f"""
            copy (
                select change, identifier_system, identifier_value, previous_location_id, location_id
                from identity_changes
                order by change, identifier_system, identifier_value, previous_location_id, location_id
            ) to '{identity_path.as_posix()}' (format csv, header true, quote '"', escape '"', null '')
            """
        )
        connection.execute(
            """
            create temporary table rekeyed as
            select previous_location_id, current_location_id
            from (
                select distinct
                    previous_location_id,
                    location_id as current_location_id
                from identity_changes
                where change = 'transition'
            ) as pairs
            qualify count(*) over (partition by previous_location_id) = 1
                and count(*) over (partition by current_location_id) = 1
            """
        )
        connection.execute(
            f"""
            create temporary table entity_changes as
            with previous_entity as (
                select
                    search.entity_id as reported_id,
                    case
                        when rekeyed.current_location_id is not null
                            then 'site:' || rekeyed.current_location_id
                        else search.entity_id
                    end as entity_id,
                    search.name
                from read_parquet('{previous_entity}') as search
                left join rekeyed
                    on search.entity_id = 'site:' || rekeyed.previous_location_id
            ),
            previous_membership as (
                select
                    links.entity_id as reported_entity_id,
                    links.location_id as reported_location_id,
                    case
                        when links.entity_id = 'site:' || rekeyed.previous_location_id
                            then 'site:' || rekeyed.current_location_id
                        else links.entity_id
                    end as entity_id,
                    coalesce(rekeyed.current_location_id, links.location_id) as location_id
                from read_parquet('{previous_link}') as links
                left join rekeyed
                    on links.location_id = rekeyed.previous_location_id
            )
            select
                'site' as record_type,
                'added' as change,
                current.location_id as record_id,
                cast(null as varchar) as previous_value,
                current.name as current_value
            from read_parquet('{current_location}') as current
            anti join read_parquet('{previous_location}') as previous
                on previous.location_id = current.location_id
            anti join rekeyed
                on rekeyed.current_location_id = current.location_id
            union all
            select
                'site',
                'removed',
                previous.location_id,
                previous.name,
                null
            from read_parquet('{previous_location}') as previous
            anti join read_parquet('{current_location}') as current
                on current.location_id = previous.location_id
            anti join rekeyed
                on rekeyed.previous_location_id = previous.location_id
            union all
            select
                'site',
                'renamed',
                current.location_id,
                previous.name,
                current.name
            from read_parquet('{current_location}') as current
            inner join rekeyed
                on rekeyed.current_location_id = current.location_id
            inner join read_parquet('{previous_location}') as previous
                on previous.location_id = rekeyed.previous_location_id
            where current.name is distinct from previous.name
            union all
            select
                'site',
                'renamed',
                current.location_id,
                previous.name,
                current.name
            from read_parquet('{current_location}') as current
            inner join read_parquet('{previous_location}') as previous
                on previous.location_id = current.location_id
            where current.name is distinct from previous.name
            union all
            select
                'entity',
                'added',
                current.entity_id,
                null,
                current.name
            from read_parquet('{current_entity}') as current
            anti join previous_entity as previous
                on previous.entity_id = current.entity_id
            union all
            select
                'entity',
                'removed',
                previous.reported_id,
                previous.name,
                null
            from previous_entity as previous
            anti join read_parquet('{current_entity}') as current
                on current.entity_id = previous.entity_id
            union all
            select
                'entity',
                'renamed',
                current.entity_id,
                previous.name,
                current.name
            from read_parquet('{current_entity}') as current
            inner join previous_entity as previous
                on previous.entity_id = current.entity_id
            where current.name is distinct from previous.name
            union all
            select
                'membership',
                'added',
                current.entity_id || '|' || current.location_id,
                null,
                null
            from read_parquet('{current_link}') as current
            anti join previous_membership as previous
                on previous.entity_id = current.entity_id
                and previous.location_id = current.location_id
            union all
            select
                'membership',
                'removed',
                previous.reported_entity_id || '|' || previous.reported_location_id,
                null,
                null
            from previous_membership as previous
            anti join read_parquet('{current_link}') as current
                on current.entity_id = previous.entity_id
                and current.location_id = previous.location_id
            """
        )
        connection.execute(
            f"""
            copy (
                select record_type, change, record_id, previous_value, current_value
                from entity_changes
                order by record_type, change, record_id
            ) to '{entity_path.as_posix()}' (format csv, header true, quote '"', escape '"', null '')
            """
        )
        identity_counts = dict(
            connection.execute(
                """
                select change, count(*)
                from identity_changes
                group by 1
                """
            ).fetchall()
        )
        entity_counts = connection.execute(
            """
            select record_type, change, count(*)
            from entity_changes
            group by 1, 2
            order by 1, 2
            """
        ).fetchall()
    finally:
        connection.close()
    summary = {
        "performed": True,
        "reason": None,
        "previous_build_id": _previous_build(previous),
        "compared_with_legacy_identifiers": legacy,
        "identity": {
            "transitions": int(identity_counts.get("transition", 0)),
            "unresolved": int(identity_counts.get("unresolved", 0)),
        },
        "changes": [
            {"record_type": record_type, "change": change, "rows": int(rows)}
            for record_type, change, rows in entity_counts
        ],
    }
    (dest / "release_diff.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
