import duckdb
import pytest

from ingest.validate import COUNTRY_MIN_ROWS, ValidationError, validate_marts, validate_raw


def _mart(path, by_country: dict[str, int], match: str = "PLACE") -> int:
    path.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    location = (path / "location.parquet").as_posix()
    search = (path / "search_entity.parquet").as_posix()
    links = (path / "entity_site.parquet").as_posix()
    blocks = []
    offset = 0
    for country, count in by_country.items():
        blocks.append(
            f"""
            select
                'id-' || (i + {offset}) as location_id,
                'Place ' || (i + {offset}) as name,
                '{match} ' || (i + {offset}) as match_string,
                'Parent' as parent_name,
                'TN24 0LZ' as postcode,
                'Ashford' as local_authority_name,
                'Kent' as health_area_name,
                '{country}' as country_name,
                case (i + {offset}) % 5
                    when 0 then 'hospital'
                    when 1 then 'care home'
                    when 2 then 'gp'
                    when 3 then 'home care'
                    else 'other'
                end as service_type
            from range({count}) as t(i)
            """
        )
        offset += count
    connection.execute(
        f"copy ({' union all '.join(blocks)}) to '{location}' (format parquet)"
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
            from range({offset}) as t(i)
        ) to '{search}' (format parquet)
        """
    )
    connection.execute(
        f"""
        copy (
            select 'site:id-' || i as entity_id, 'id-' || i as location_id
            from range({offset}) as t(i)
        ) to '{links}' (format parquet)
        """
    )
    connection.close()
    return offset


def test_raw_files_must_exist(tmp_path):
    with pytest.raises(ValidationError) as caught:
        validate_raw(tmp_path)
    assert "ods/etr.csv is missing" in caught.value.failures


def test_small_mart_fails_the_floor(tmp_path):
    _mart(tmp_path, {"England": 10})
    with pytest.raises(ValidationError) as caught:
        validate_marts(tmp_path, None, force=False)
    assert any("needs" in failure and "location" in failure for failure in caught.value.failures)


def test_mart_band_and_force(tmp_path):
    rows = _mart(tmp_path, COUNTRY_MIN_ROWS)
    previous = {"row_counts": {"location": rows + 1_000}}
    counts = validate_marts(tmp_path, previous, force=False)
    assert counts["location"] == rows

    jumped = tmp_path / "jumped"
    jumped_rows = _mart(jumped, {name: count + 20_000 for name, count in COUNTRY_MIN_ROWS.items()})
    with pytest.raises(ValidationError) as caught:
        validate_marts(jumped, {"row_counts": {"location": rows}}, force=False)
    assert any("outside" in failure for failure in caught.value.failures)
    validate_marts(jumped, {"row_counts": {"location": rows}}, force=True)
    assert jumped_rows > rows
