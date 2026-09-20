from __future__ import annotations

from ashare2026.data.manager import DataBundle
from ashare2026.models.board import BoardQuote
from ashare2026.models.market import EtfQuote, IndexQuote, LimitStock, MarketSnapshot, StockQuote
from ashare2026.timeutil import isoformat_cn


def stock(code, name, pct, amount, inflow, **kwargs) -> StockQuote:
    return StockQuote(
        code=code,
        name=name,
        change_pct=pct,
        open_pct=kwargs.get("open_pct", pct / 3),
        amount=amount,
        net_inflow=inflow,
        market_cap=kwargs.get("market_cap", 8e10),
        is_limit_up=kwargs.get("is_limit_up", pct >= 9.5),
        is_20cm=kwargs.get("is_20cm", code.startswith("300") or code.startswith("688")),
        consecutive_boards=kwargs.get("boards", 0),
        is_one_word=kwargs.get("one_word", False),
        industry=kwargs.get("industry"),
        concepts=kwargs.get("concepts", []),
        source="fixture",
    )


def board(code, name, kind, pct, amount, inflow, members, **kwargs) -> BoardQuote:
    return BoardQuote(
        code=code,
        name=name,
        kind=kind,
        change_pct=pct,
        amount=amount,
        up_count=kwargs.get("up", 20),
        down_count=kwargs.get("down", 5),
        leader_name=members[0].name if members else None,
        leader_code=members[0].code if members else None,
        leader_change_pct=members[0].change_pct if members else None,
        net_inflow=inflow,
        net_inflow_5d=kwargs.get("flow5", inflow * 2),
        main_buy=abs(inflow) * 1.6 if inflow else None,
        main_sell=(abs(inflow) * 1.6 - inflow) if inflow else None,
        source="fixture",
        constituents=members,
    )


def make_bundle() -> DataBundle:
    cpo = [
        stock("300308", "中际旭创", 8.2, 2.7e10, 1.6e9, concepts=["CPO"], industry="通信设备", boards=0),
        stock("300502", "新易盛", 7.1, 1.8e10, 9.2e8, concepts=["CPO", "光模块"], industry="通信设备"),
        stock("002281", "光迅科技", 5.4, 6.2e9, 3.1e8, concepts=["光模块"]),
        stock("300394", "天孚通信", 10.0, 7.5e9, 4.4e8, concepts=["CPO"], is_limit_up=True, is_20cm=True, boards=2),
        stock("688498", "源杰科技", 12.0, 3.3e9, 1.1e8, concepts=["光芯片"], is_20cm=True),
    ]
    robot = [
        stock("002008", "大族激光", 4.2, 4.1e9, 2.0e8, concepts=["人形机器人"], industry="专用设备"),
        stock("002472", "双环传动", 6.8, 3.8e9, 2.6e8, concepts=["减速器", "机器人"]),
        stock("300124", "汇川技术", 3.1, 5.0e9, 1.4e8, concepts=["机器人"]),
        stock("603728", "鸣志电器", 9.9, 2.2e9, 1.8e8, concepts=["机器人"], is_limit_up=True, boards=1),
    ]
    bank = [
        stock("600036", "招商银行", -1.2, 3.0e9, -4.5e8, industry="银行", concepts=["银行"]),
        stock("601398", "工商银行", -0.8, 2.2e9, -2.1e8, industry="银行", concepts=["银行"]),
        stock("601288", "农业银行", -2.1, 1.8e9, -3.3e8, industry="银行"),
    ]
    weak = [
        stock("000001", "平安银行", -3.4, 1.5e9, -6.0e8, industry="银行", concepts=["银行"]),
        stock("601229", "上海银行", -7.2, 9.0e8, -2.8e8, industry="银行"),
    ]
    concepts = [
        board("BK1127", "CPO概念", "concept", 4.8, 4.2e10, 8.5e9, cpo, flow5=1.2e10),
        board("BK1184", "光模块", "concept", 3.9, 2.1e10, 3.3e9, cpo[:3], flow5=5.0e9),
        board("BK0891", "国产芯片", "concept", 2.1, 1.5e10, 2.2e9, [], flow5=2.8e9),
        board("BK1610", "人形机器人", "concept", 3.3, 1.8e10, 1.7e9, robot, flow5=2.0e9),
        board("BK0475", "银行", "concept", -1.8, 9.0e9, -3.5e9, bank + weak, flow5=-6.0e9),
    ]
    industries = [
        board("BK0447", "通信设备", "industry", 3.6, 5.0e10, 6.0e9, cpo, flow5=9.0e9),
        board("BK0475I", "银行", "industry", -1.5, 1.2e10, -4.0e9, bank, flow5=-7.0e9),
        board("BK0736", "专用设备", "industry", 2.4, 1.6e10, 1.1e9, robot, flow5=1.5e9),
    ]
    snapshot = MarketSnapshot(
        indices={
            "000001": IndexQuote(code="000001", name="上证指数", price=3911, change_pct=0.94, open_pct=0.42, amount=9.9e11, up_count=1756, down_count=519, source="fixture"),
            "399001": IndexQuote(code="399001", name="深证成指", price=13640, change_pct=1.72, open_pct=1.15, amount=1.08e12, up_count=2224, down_count=611, source="fixture"),
            "399006": IndexQuote(code="399006", name="创业板指", price=3372, change_pct=2.25, open_pct=1.61, amount=5.2e11, source="fixture"),
            "000300": IndexQuote(code="000300", name="沪深300", price=4507, change_pct=1.06, open_pct=0.51, source="fixture"),
            "000852": IndexQuote(code="000852", name="中证1000", price=6200, change_pct=1.8, open_pct=0.9, source="fixture"),
        },
        stocks=cpo + robot + bank + weak,
        limit_up=[
            LimitStock(code="300394", name="天孚通信", change_pct=20.0, amount=7.5e9, consecutive_boards=2, industry="通信设备", is_20cm=True, is_one_word=False),
            LimitStock(code="603728", name="鸣志电器", change_pct=9.9, amount=2.2e9, consecutive_boards=1, industry="专用设备"),
        ],
        limit_down=[],
        etfs=[
            EtfQuote(code="159819", name="人工智能ETF", change_pct=2.1, amount=3.2e9, net_inflow_5d=8.0e8, net_inflow_10d=1.1e9, source="fixture"),
            EtfQuote(code="515880", name="通信ETF", change_pct=1.8, amount=2.1e9, net_inflow_5d=5.0e8, source="fixture"),
            EtfQuote(code="512800", name="银行ETF", change_pct=-1.4, amount=9.0e8, net_inflow_5d=-4.0e8, source="fixture"),
            EtfQuote(code="562500", name="机器人ETF", change_pct=1.5, amount=1.2e9, net_inflow_5d=2.2e8, source="fixture"),
        ],
        total_amount=2.07e12,
        up_count=3980,
        down_count=1130,
        limit_up_count=78,
        limit_down_count=2,
        consecutive_count=12,
        cm20_count=9,
        source_notes=["fixture"],
    )
    return DataBundle(
        snapshot=snapshot,
        industries=industries,
        concepts=concepts,
        source_map={
            "quotes": "fixture",
            "indices": "fixture",
            "limits": "fixture",
            "industry": "fixture",
            "concept": "fixture",
            "concept_flow": "fixture",
            "stock_fund": "fixture",
            "flow_5d": "fixture",
            "etf": "fixture",
            "tags": "fixture",
        },
        notes=["测试夹具，非实时行情"],
        flow_3d_ok=False,
        flow_5d_ok=True,
        reasons_ok=False,
        tags_ok=True,
        new_high_ok=False,
        etf_share_ok=False,
        quote_timestamp=isoformat_cn(),
    )
