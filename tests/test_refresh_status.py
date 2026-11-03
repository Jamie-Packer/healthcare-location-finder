from ingest.contract import SCHEMA_VERSION, contract_sha256
from ingest.refresh import Landed, _manifest, _same_contract, build_status, coverage_effect
from ingest.registry import SPECS


def _landed(status: str) -> Landed:
    return Landed(SPECS[0], None, status, checked_at="2026-01-01T00:00:00+00:00")


def test_build_status_distinguishes_a_reused_source_from_a_missing_one():
    assert build_status({"ok"}) == "normal"
    assert coverage_effect("ok") == "included"
    assert build_status({"ok", "fallback"}) == "degraded"
    assert coverage_effect("fallback") == "last_good_copy"
    assert build_status({"ok", "missing"}) == "partial"
    assert coverage_effect("missing") == "omitted"


def test_manifest_records_a_degraded_source():
    manifest = _manifest(
        [_landed("ok"), Landed(SPECS[1], None, "fallback", error="timed out", checked_at="2026-01-01T00:00:00+00:00")],
        {},
        {"location": 1},
        3,
    )
    assert manifest["build_status"] == "degraded"
    assert manifest["schema_version"] == "1.0.0"
    assert manifest["contract_sha256"] == contract_sha256()
    assert isinstance(manifest["worktree_dirty"], bool)
    assert manifest["data_scope"] == "current"
    assert manifest["validation"]["conflicts"] == 3
    fallback = manifest["sources"][1]
    assert fallback["coverage_effect"] == "last_good_copy"
    assert fallback["error"] == "timed out"
    assert fallback["checked_at"] == "2026-01-01T00:00:00+00:00"


def test_an_old_contract_is_not_treated_as_current():
    current = {"schema_version": SCHEMA_VERSION, "contract_sha256": contract_sha256()}
    assert _same_contract(current)
    assert not _same_contract({})
    assert not _same_contract({"schema_version": SCHEMA_VERSION})
    assert not _same_contract({"schema_version": "0.0.0", "contract_sha256": contract_sha256()})
