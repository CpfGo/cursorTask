from ashare2026.data.availability import build_availability
from ashare2026.constants import DATA_MISSING
from tests.fixtures_data import make_bundle


def test_availability_rows_complete():
    bundle = make_bundle()
    rows = build_availability(
        snapshot=bundle.snapshot,
        industries=bundle.industries,
        concepts=bundle.concepts,
        flow_3d_ok=False,
        flow_5d_ok=True,
        reasons_ok=False,
        tags_ok=True,
        new_high_ok=False,
        etf_share_ok=False,
        source_map=bundle.source_map,
        timestamp=bundle.quote_timestamp,
    )
    assert len(rows) == 14
    missing_3d = next(r for r in rows if "3日" in r.item)
    assert missing_3d.available is False
    assert missing_3d.actual_source == DATA_MISSING
    assert next(r for r in rows if r.item == "概念5日流入").available is True
