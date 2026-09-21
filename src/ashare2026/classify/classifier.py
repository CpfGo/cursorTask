from __future__ import annotations

from collections import defaultdict

from ashare2026.constants import CHAIN_KEYWORDS, CHAIN_NAMES, DATA_MISSING
from ashare2026.models.board import BoardQuote
from ashare2026.models.chain import ChainBucket
from ashare2026.models.market import MarketSnapshot, StockQuote


def classify_text(*parts: str | None) -> str:
    blob = " ".join(p for p in parts if p)
    if not blob:
        return "其他"
    scores: dict[str, int] = {}
    for chain, keys in CHAIN_KEYWORDS.items():
        hit = sum(1 for k in keys if k and k in blob)
        if hit:
            scores[chain] = hit * 10 + max(len(k) for k in keys if k in blob)
    if not scores:
        return "其他"
    return max(scores, key=scores.get)


def classify_board(board: BoardQuote) -> str:
    return classify_text(board.name, board.leader_name)


def merge_stocks(snapshot: MarketSnapshot, boards: list[BoardQuote]) -> list[StockQuote]:
    by_code: dict[str, StockQuote] = {}
    for stock in snapshot.stocks:
        by_code[stock.code] = stock.model_copy(deep=True)
    for board in boards:
        for raw in board.constituents:
            if raw.code in by_code:
                cur = by_code[raw.code]
                if board.kind == "concept" and board.name not in cur.concepts:
                    cur.concepts.append(board.name)
                if board.kind == "industry" and not cur.industry:
                    cur.industry = board.name
                if cur.net_inflow is None:
                    cur.net_inflow = raw.net_inflow
                if cur.amount is None:
                    cur.amount = raw.amount
            else:
                stock = raw.model_copy(deep=True)
                if board.kind == "industry":
                    stock.industry = stock.industry or board.name
                if board.kind == "concept" and board.name not in stock.concepts:
                    stock.concepts.append(board.name)
                by_code[stock.code] = stock
    for item in snapshot.limit_up:
        stock = by_code.get(item.code)
        if stock is None:
            stock = StockQuote(
                code=item.code,
                name=item.name,
                change_pct=item.change_pct,
                amount=item.amount,
                net_inflow=item.fund,
                industry=item.industry,
                is_limit_up=True,
                consecutive_boards=item.consecutive_boards,
                is_one_word=item.is_one_word,
                is_20cm=item.is_20cm,
                limit_reason=item.reason,
                source="limit_pool",
            )
            by_code[item.code] = stock
        else:
            stock.is_limit_up = True
            stock.consecutive_boards = max(stock.consecutive_boards, item.consecutive_boards)
            stock.is_one_word = stock.is_one_word or item.is_one_word
            stock.industry = stock.industry or item.industry
            stock.limit_reason = stock.limit_reason or item.reason
    return list(by_code.values())


def classify_chains(
    snapshot: MarketSnapshot,
    industries: list[BoardQuote],
    concepts: list[BoardQuote],
    total_amount: float | None,
) -> list[ChainBucket]:
    boards = industries + concepts
    stocks = merge_stocks(snapshot, boards)
    board_chain = {b.name: classify_board(b) for b in boards}
    board_weight = {b.name: (b.net_inflow or 0) + (b.amount or 0) / 50 for b in boards}

    grouped: dict[str, list[StockQuote]] = defaultdict(list)
    mapped: dict[str, set[str]] = defaultdict(set)

    for stock in stocks:
        weights: dict[str, float] = defaultdict(float)
        tags = [*stock.concepts, stock.industry, stock.limit_reason, stock.name]
        for tag in tags:
            if not tag:
                continue
            chain = board_chain.get(tag) or classify_text(tag)
            w = board_weight.get(tag, 1.0)
            weights[chain] += w
            if tag in board_chain:
                mapped[chain].add(tag)
        if not weights:
            chain = "其他"
        else:
            chain = max(weights, key=weights.get)
        if chain not in CHAIN_NAMES:
            chain = "其他"
        stock.chain = chain if chain != "其他" else (stock.chain or "其他")
        if chain == "其他" and not any(tags):
            stock.chain = f"其他 / {DATA_MISSING}"
        else:
            stock.chain = chain
        grouped[stock.chain].append(stock)

    buckets: list[ChainBucket] = []
    for name, members in grouped.items():
        amount = sum(s.amount or 0 for s in members) or None
        inflow = sum(s.net_inflow or 0 for s in members) if any(s.net_inflow is not None for s in members) else None
        share = None
        if amount is not None and total_amount:
            share = amount / total_amount * 100
        members.sort(key=lambda s: (s.amount or 0, s.net_inflow or 0), reverse=True)
        buckets.append(
            ChainBucket(
                name=name,
                mapped_boards=sorted(mapped.get(name, set())),
                stocks=members,
                amount=amount,
                amount_share=share,
                net_inflow=inflow,
            )
        )
    buckets.sort(key=lambda b: (b.amount or 0), reverse=True)
    return buckets
