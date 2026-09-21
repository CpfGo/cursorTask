from ashare2026.constants import DATA_MISSING, FUND_STAGES, INDUSTRY_CYCLES, MARKET_STATES, OPEN_ENVIRONMENTS, POSITIONS
from ashare2026.pipeline.engine import run_pipeline
from ashare2026.pipeline.step0_auction import _open_env
from ashare2026.pipeline.step1_market import run_step1
from tests.fixtures_data import make_bundle


def test_pipeline_from_fixture():
    result = run_pipeline(make_bundle())
    assert result.headline.first_chain != ""
    assert result.scores
    assert result.scores[0].chain in {c.name for c in result.chains}
    assert result.position.position in POSITIONS
    assert result.market.state in MARKET_STATES
    assert result.auction.open_environment in OPEN_ENVIRONMENTS
    assert result.auction.split_missing.startswith("DATA_MISSING")
    for cycle in result.cycles:
        assert cycle.industry_cycle in INDUSTRY_CYCLES
        assert cycle.fund_stage in FUND_STAGES


def test_three_day_not_invented():
    result = run_pipeline(make_bundle())
    assert all(row.rank_3d is None for row in result.continuity)
    assert any(DATA_MISSING in (c.continuity_3d or "") for c in result.chains)


def test_three_day_rank_when_present():
    bundle = make_bundle()
    bundle.flow_3d_ok = True
    for i, board in enumerate(bundle.concepts):
        board.net_inflow_3d = (len(bundle.concepts) - i) * 1e9
    result = run_pipeline(bundle)
    ranked = [row for row in result.continuity if row.rank_3d is not None]
    assert ranked
    assert ranked[0].name == bundle.concepts[0].name
    assert any(c.rank_3d == 1 for c in result.chains)


def test_limit_reason_marked_missing():
    result = run_pipeline(make_bundle())
    reason = next(r for r in result.availability if r.item == "涨停原因")
    assert reason.available is False


def test_limit_reason_available_when_present():
    bundle = make_bundle()
    bundle.snapshot.limit_up[0].reason = "光模块"
    bundle.reasons_ok = True
    bundle.source_map["limit_reason"] = "同花顺涨停雷达/复盘原文"
    result = run_pipeline(bundle)
    reason = next(r for r in result.availability if r.item == "涨停原因")
    assert reason.available is True
    assert "同花顺" in (reason.actual_source or "")


def test_open_environment_four_choices():
    assert _open_env(-2.0, 10, 80, 0, 12) == "风险开盘"
    assert _open_env(0.8, 80, 10, 8, 0) == "强开盘"
    assert _open_env(-0.4, 10, 40, 1, 0) == "弱开盘"
    assert _open_env(0.1, 20, 18, 2, 1) == "正常开盘"


def test_market_states_use_table():
    bundle = make_bundle()
    env = run_step1(bundle.snapshot)
    assert env.state in MARKET_STATES
    assert "上涨" in env.reason
