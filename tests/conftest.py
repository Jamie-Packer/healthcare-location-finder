import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def fixture_mart() -> Path:
    os.environ["LOCATIONS_MART_DIR"] = str(ROOT / "data" / "build" / "fixture-mart")
    from ingest.build import dbt_build

    return dbt_build(fixtures=True)
