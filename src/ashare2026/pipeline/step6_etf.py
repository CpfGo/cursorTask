from __future__ import annotations

from ashare2026.constants import DATA_MISSING, ETF_KEYWORDS
from ashare2026.models.chain import ChainBucket, EtfChainRow
from ashare2026.models.market import EtfQuote, MarketSnapshot


def run_step6(chains: list[ChainBucket], snapshot: MarketSnapshot) -> list[EtfChainRow]:
    etfs = snapshot.etfs
    total_etf_amount = sum(e.amount or 0 for e in etfs) or None
    rows: list[EtfChainRow] = []
    for chain in [c for c in chains if not c.name.startswith("其他")][:10]:
        keys = ETF_KEYWORDS.get(chain.name, (chain.name,))
        picked = _pick_etf(etfs, keys)
        if not etfs:
            rows.append(
                EtfChainRow(
                    chain=chain.name,
                    etf_name=DATA_MISSING,
                    note=DATA_MISSING,
                )
            )
            continue
        if picked is None:
            rows.append(
                EtfChainRow(
                    chain=chain.name,
                    etf_name="无直接对应ETF",
                    note="无直接对应ETF",
                )
            )
            continue
        share = None
        if picked.amount is not None and total_etf_amount:
            share = picked.amount / total_etf_amount * 100
        flow20 = DATA_MISSING
        purchase = DATA_MISSING
        rows.append(
            EtfChainRow(
                chain=chain.name,
                etf_name=picked.name,
                etf_code=picked.code,
                amount=picked.amount,
                amount_share=share,
                change_pct=picked.change_pct,
                flow_5d=picked.net_inflow_5d,
                flow_10d=picked.net_inflow_10d,
                flow_20d=None,
                purchase_rank=purchase,
                note="" if picked.net_inflow_5d is not None else "份额/净申购 DATA_MISSING",
            )
        )
        _ = flow20
    return rows


def _pick_etf(etfs: list[EtfQuote], keys: tuple[str, ...]) -> EtfQuote | None:
    scored: list[tuple[int, float, EtfQuote]] = []
    for etf in etfs:
        hit = sum(1 for k in keys if k and k in etf.name)
        if hit:
            scored.append((hit, etf.amount or 0, etf))
    if not scored:
        return None
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return scored[0][2]
