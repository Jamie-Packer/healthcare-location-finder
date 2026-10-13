import uuid

import duckdb

from ingest.build import database_path, dbt_build
from ingest.history import export_history, restore_history


def test_closed_snapshot_row_survives_the_next_build(fixture_mart, tmp_path):
    token = "extra-" + uuid.uuid4().hex
    database = database_path(fixtures=True)
    original = tmp_path / "original.parquet"
    export_history(database, original)
    modified = tmp_path / "modified.parquet"
    connection = duckdb.connect()
    connection.execute(
        f"""
        copy (
            select * from read_parquet('{original.as_posix()}')
            union all by name
            select * from (
                select
                    location_id,
                    name,
                    parent_name,
                    postcode,
                    ods_code,
                    '{token}' as dbt_scd_id,
                    dbt_updated_at,
                    dbt_valid_from,
                    dbt_valid_from as dbt_valid_to
                from read_parquet('{original.as_posix()}')
                limit 1
            )
        ) to '{modified.as_posix()}' (format parquet)
        """
    )
    connection.close()
    assert restore_history(database, modified)
    dbt_build(fixtures=True)
    exported = tmp_path / "after.parquet"
    export_history(database, exported)
    found = duckdb.sql(
        f"select count(*) from read_parquet('{exported.as_posix()}') where dbt_scd_id = '{token}'"
    ).fetchone()[0]
    assert found == 1
