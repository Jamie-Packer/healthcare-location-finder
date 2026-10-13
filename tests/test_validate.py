import duckdb
import pytest

from ingest.validate import LOCATION_MIN_ROWS, ValidationError, validate_marts, validate_raw


def _mart(path, rows: int, country: str = "England", match: str = "PLACE") -> None:
    path.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    location = (path / "location.parquet").as_posix()
    search = (path / "search_entity.parquet").as_posix()
    links = (path / "entity_site.parquet").as_posix()
    connection.execute(
        f"""
        copy (
            select
                'id-' || i as location_id,
                'Place ' || i as name,
                '{match}' || i as match_string,
                'Parent' as parent_name,
                'TN24 0LZ' as postcode,
                'Ashford' as local_authority_name,
                '{country}' as country_name,
                case i % 4
                    when 0 then 'hospital'
                    when 1 then 'care home'
                    when 2 then 'gp'
                    else 'other'
                end as service_type
            from range({rows}) as t(i)
        ) to '{location}' (format parquet)
        """
    )
    connection.execute(
        f"""
        copy (
            select 'country:England' as entity_id, 'country' as entity_type, 'England' as name
            union all
            select 'region:E12000008', 'region', 'South East'
            union all
            select 'provider:RXX', 'provider', 'Parent'
            union all
            select 'site:id-' || i, 'site', 'Place ' || i
            from range({rows}) as t(i)
        ) to '{search}' (format parquet)
        """
    )
    connection.execute(
        f"""
        copy (
            select 'site:id-' || i as entity_id, 'id-' || i as location_id
            from range({rows}) as t(i)
        ) to '{links}' (format parquet)
        """
    )
    connection.close()


def test_raw_files_must_exist(tmp_path):
    with pytest.raises(ValidationError) as caught:
        validate_raw(tmp_path)
    assert "ods/etr.csv is missing" in caught.value.failures


def test_small_mart_fails_the_floor(tmp_path):
    _mart(tmp_path, 10)
    with pytest.raises(ValidationError) as caught:
        validate_marts(tmp_path, None, force=False)
    assert any("needs" in failure and "location" in failure for failure in caught.value.failures)


def test_mart_band_and_force(tmp_path):
    _mart(tmp_path, LOCATION_MIN_ROWS)
    previous = {"row_counts": {"location": LOCATION_MIN_ROWS + 1_000}}
    counts = validate_marts(tmp_path, previous, force=False)
    assert counts["location"] == LOCATION_MIN_ROWS

    jumped = tmp_path / "jumped"
    _mart(jumped, LOCATION_MIN_ROWS + 20_000)
    with pytest.raises(ValidationError) as caught:
        validate_marts(jumped, {"row_counts": {"location": LOCATION_MIN_ROWS}}, force=False)
    assert any("outside" in failure for failure in caught.value.failures)
    validate_marts(jumped, {"row_counts": {"location": LOCATION_MIN_ROWS}}, force=True)
