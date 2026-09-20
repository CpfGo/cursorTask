from __future__ import annotations

from ashare2026.classify.classifier import classify_chains
from ashare2026.config import load_settings
from ashare2026.constants import DATA_MISSING, DATA_INSUFFICIENT_BANNER
from ashare2026.data.availability import build_availability
from ashare2026.data.manager import DataBundle, DataManager
from ashare2026.formatting import yi
from ashare2026.models.chain import ChainBucket
from ashare2026.models.report import (
    FundRoadmap,
    Headline,
    MainlineCard,
    OneLiner,
    PipelineResult,
    ReportMeta,
)
from ashare2026.pipeline.step0_auction import run_step0
from ashare2026.pipeline.step1_market import run_step1
from ashare2026.pipeline.step2_boards import run_step2
from ashare2026.pipeline.step3_serenity import run_step3
from ashare2026.pipeline.step4_leaders import run_step4
from ashare2026.pipeline.step5_echelon import run_step5
from ashare2026.pipeline.step6_etf import run_step6
from ashare2026.pipeline.step7_cycle import run_step7
from ashare2026.pipeline.step8_score import run_step8
from ashare2026.pipeline.step9_weak import run_step9
from ashare2026.pipeline.step10_position import run_step10
from ashare2026.pipeline.step11_falsify import run_step11
from ashare2026.timeutil import isoformat_cn, now_cn


def run_pipeline(bundle: DataBundle | None = None) -> PipelineResult:
    settings = load_settings()
    bundle = bundle or DataManager().fetch()
    snapshot = bundle.snapshot
    industries, concepts, flows, continuity = run_step2(
        bundle.industries,
        bundle.concepts,
        bundle.flow_3d_ok,
        bundle.flow_5d_ok,
        settings.pipeline.industry_top_n,
    )
    chains = classify_chains(snapshot, bundle.industries, bundle.concepts, snapshot.total_amount)
    _attach_continuity(chains, continuity, bundle.concepts)
    auction = run_step0(snapshot, bundle.industries, bundle.concepts)
    market = run_step1(snapshot)
    scarcity = run_step3(chains)
    leaders, mids, follows = run_step4(chains, scarcity)
    echelons, money = run_step5(chains, leaders, mids, follows)
    etfs = run_step6(chains, snapshot)
    cycles = run_step7(chains, echelons, money)
    cont_scores = _continuity_scores(chains)
    scores = run_step8(chains, leaders, echelons, money, etfs, cont_scores)
    weakest = run_step9(chains, bundle.industries, bundle.concepts)
    flow_label = _flow_label(scores, chains)
    continuity_label = _best_continuity(continuity)
    money_label = _money_label(money)
    leader_label = _leader_label(leaders)
    position = run_step10(
        auction,
        market,
        scores,
        cycles,
        continuity_label,
        money_label,
        leader_label,
        flow_label,
    )
    falsify = run_step11(scores, cycles)

    availability = build_availability(
        snapshot=snapshot,
        industries=bundle.industries,
        concepts=bundle.concepts,
        flow_3d_ok=bundle.flow_3d_ok,
        flow_5d_ok=bundle.flow_5d_ok,
        reasons_ok=bundle.reasons_ok,
        tags_ok=bundle.tags_ok,
        new_high_ok=bundle.new_high_ok,
        etf_share_ok=bundle.etf_share_ok,
        source_map=bundle.source_map,
        timestamp=bundle.quote_timestamp,
    )
    missing_core = sum(
        1
        for row in availability
        if not row.available
        and row.item in {"全A实时行情", "指数实时行情", "行业成交额", "概念成交额", "概念即时流入"}
    )
    insufficient = missing_core >= 2 or not chains

    first, second, third = _cards(scores, cycles, scarcity, leaders, mids, follows, falsify, chains)
    headline = Headline(
        auction_strongest=(auction.strongest.board if auction.strongest else DATA_MISSING),
        auction_second=(auction.second.board if auction.second else DATA_MISSING),
        auction_third=(auction.third.board if auction.third else DATA_MISSING),
        auction_weakest=(auction.weakest.board if auction.weakest else DATA_MISSING),
        open_state=auction.open_environment or DATA_MISSING,
        participation=auction.participation or DATA_MISSING,
        first_chain=first.chain or DATA_MISSING,
        weakest=weakest[0].name if weakest else DATA_MISSING,
        market_state=market.state,
        position=position.position,
    )
    roadmap = FundRoadmap(
        auction_attack=headline.auction_strongest,
        intraday_flow=first.chain or DATA_MISSING,
        spreading_to=second.chain or DATA_MISSING,
        avoiding=headline.weakest,
    )
    if insufficient:
        roadmap = FundRoadmap(
            auction_attack=f"{DATA_MISSING}，不判断" if headline.auction_strongest == DATA_MISSING else roadmap.auction_attack,
            intraday_flow=roadmap.intraday_flow,
            spreading_to=roadmap.spreading_to,
            avoiding=roadmap.avoiding,
        )
    one = OneLiner(
        auction_strongest=headline.auction_strongest,
        incremental_chain=first.chain or DATA_MISSING,
        fund_stage=first.fund_stage or DATA_MISSING,
        weakest=headline.weakest,
        worth_holding=_worth(position.position, first.chain),
    )
    meta = ReportMeta(
        generated_at=isoformat_cn(now_cn()),
        quote_timestamp=bundle.quote_timestamp,
        title=settings.app.report_title,
        version=settings.app.version,
        insufficient=insufficient,
    )
    return PipelineResult(
        meta=meta,
        availability=availability,
        snapshot=snapshot,
        auction=auction,
        market=market,
        industries=industries,
        concepts=concepts,
        concept_flows=flows,
        continuity=continuity,
        chains=chains,
        scarcity=scarcity,
        leaders=leaders,
        mids=mids,
        follows=follows,
        echelons=echelons,
        money=money,
        etfs=etfs,
        cycles=cycles,
        scores=scores,
        weakest=weakest,
        position=position,
        falsify=falsify,
        headline=headline,
        first=first,
        second=second,
        third=third,
        weak_card=weakest[0] if weakest else None,
        roadmap=roadmap,
        one_liner=one,
        source_notes=bundle.notes + ([DATA_INSUFFICIENT_BANNER] if insufficient else []),
    )


def _attach_continuity(chains: list[ChainBucket], continuity, concepts) -> None:
    by_name = {c.name: c for c in continuity}
    for chain in chains:
        ranks_i, ranks_5 = [], []
        for board in chain.mapped_boards:
            row = by_name.get(board)
            if not row:
                continue
            if row.instant_rank:
                ranks_i.append(row.instant_rank)
            if row.rank_5d:
                ranks_5.append(row.rank_5d)
        chain.instant_rank = min(ranks_i) if ranks_i else None
        chain.rank_5d = min(ranks_5) if ranks_5 else None
        chain.rank_3d = None
        if chain.rank_5d:
            chain.continuity_5d = f"5日排名{chain.rank_5d}"
        else:
            chain.continuity_5d = DATA_MISSING
        chain.continuity_3d = DATA_MISSING


def _continuity_scores(chains: list[ChainBucket]) -> dict[str, float]:
    out: dict[str, float] = {}
    for chain in chains:
        score = 0.0
        if chain.instant_rank and chain.instant_rank <= 10:
            score += 50
        elif chain.instant_rank and chain.instant_rank <= 20:
            score += 35
        if chain.rank_5d and chain.rank_5d <= 10:
            score += 50
        elif chain.rank_5d and chain.rank_5d <= 20:
            score += 35
        out[chain.name] = min(100, score)
    return out


def _cards(scores, cycles, scarcity, leaders, mids, follows, falsify, chains) -> tuple[MainlineCard, MainlineCard, MainlineCard]:
    cards = []
    for i in range(3):
        if i >= len(scores):
            cards.append(MainlineCard(chain=DATA_MISSING, cycle=DATA_MISSING, fund_stage=DATA_MISSING, scarce_link=DATA_MISSING, instant_flow=DATA_MISSING, continuity=DATA_MISSING, leader=DATA_MISSING, mids=DATA_MISSING, follows=DATA_MISSING, falsify=DATA_MISSING))
            continue
        item = scores[i]
        chain = next((c for c in chains if c.name == item.chain), None)
        cycle = next((c for c in cycles if c.chain == item.chain), None)
        scarce = next((c for c in scarcity if c.chain == item.chain), None)
        lead = next((c for c in leaders if c.chain == item.chain), None)
        mid = "、".join(x.name for x in mids if x.chain == item.chain) or DATA_MISSING
        fol = "、".join(x.name for x in follows if x.chain == item.chain) or DATA_MISSING
        fal = next((c for c in falsify if c.chain == item.chain), None)
        cards.append(
            MainlineCard(
                chain=item.chain,
                cycle=cycle.industry_cycle if cycle else DATA_MISSING,
                fund_stage=cycle.fund_stage if cycle else DATA_MISSING,
                scarce_link=scarce.scarce_link if scarce else DATA_MISSING,
                instant_flow=yi(chain.net_inflow) if chain else DATA_MISSING,
                continuity=f"3日{DATA_MISSING}；{chain.continuity_5d if chain else DATA_MISSING}",
                leader=lead.name if lead else DATA_MISSING,
                mids=mid,
                follows=fol,
                falsify="；".join(fal.conditions[:3]) if fal else DATA_MISSING,
            )
        )
    return cards[0], cards[1], cards[2]


def _flow_label(scores, chains) -> str:
    if not scores:
        return DATA_MISSING
    chain = next((c for c in chains if c.name == scores[0].chain), None)
    if chain is None or chain.net_inflow is None:
        return DATA_MISSING
    if chain.net_inflow > 0:
        return "流入"
    return "流出"


def _best_continuity(continuity) -> str:
    if not continuity:
        return DATA_MISSING
    ratings = [c.rating for c in continuity if c.rating and c.rating != DATA_MISSING]
    for prefer in ("强连续", "趋势资金", "短线攻击", "一日游", "资金退潮"):
        if prefer in ratings:
            return prefer
    return DATA_MISSING


def _money_label(money) -> str:
    if not money:
        return DATA_MISSING
    top = max(m.score for m in money)
    if top >= 3.5:
        return "强"
    if top >= 2:
        return "中"
    if top > 0:
        return "弱"
    return "差"


def _leader_label(leaders) -> str:
    if not leaders:
        return DATA_MISSING
    lead = leaders[0]
    if lead.amount is None:
        return DATA_MISSING
    if "涨停" in (lead.limit_flag or ""):
        return "强"
    return "中"


def _worth(position: str, chain: str) -> str:
    if chain == DATA_MISSING:
        return f"{DATA_MISSING}，不判断是否值得继续配置"
    if position == "激进":
        return "资金强度支持继续跟踪当前主线，不构成买卖指令"
    if position == "正常":
        return "资金强度允许维持观察与配置环境，不构成买卖指令"
    if position == "谨慎":
        return "资金强度一般，降低配置环境，不构成买卖指令"
    return "资金强度偏弱，以防守环境为主，不构成买卖指令"
