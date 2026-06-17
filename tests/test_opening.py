"""开盘买点与热点评分单元测试"""

from datetime import datetime

import pandas as pd

from src.hot_sector import HotSectorAnalyzer
from src.models import BoardType, LimitUpStock
from src.opening_monitor import OpeningMonitor


def _make_stock(**kwargs) -> LimitUpStock:
    defaults = dict(
        code="000001",
        name="测试股",
        board_type=BoardType.FIRST,
        close_price=10.0,
        limit_up_price=11.0,
        volume=1e6,
        float_market_cap=50.0,
        consecutive_days=1,
        trade_date="20250616",
        sector="人工智能",
    )
    defaults.update(kwargs)
    return LimitUpStock(**defaults)


class TestOpeningMonitor:
    def _monitor(self) -> OpeningMonitor:
        hot = HotSectorAnalyzer(require_hot_sector=False)
        hot._hot_sectors = ["人工智能"]
        hot._sector_stocks = {"人工智能": {"000001"}}
        hot._fund_flow_cache = {"000001": 1200.0}
        return OpeningMonitor(hot_sector=hot)

    def test_high_open_in_range(self):
        m = self._monitor()
        spot = pd.DataFrame([{
            "代码": "000001",
            "昨收": 10.0,
            "今开": 10.45,
            "最新价": 10.80,
            "换手率": 12.5,
        }])
        stock = _make_stock()
        sig = m._evaluate(stock, spot, datetime(2025, 6, 17, 9, 35), False)
        assert sig is not None
        assert 3.0 <= sig.open_gain_pct <= 6.0
        assert sig.current_gain_pct >= 7.0

    def test_reject_low_open(self):
        m = self._monitor()
        spot = pd.DataFrame([{
            "代码": "000001",
            "昨收": 10.0,
            "今开": 10.10,
            "最新价": 10.80,
            "换手率": 12.0,
        }])
        assert m._evaluate(_make_stock(), spot, datetime.now(), False) is None

    def test_reject_gain_below_threshold(self):
        m = self._monitor()
        spot = pd.DataFrame([{
            "代码": "000001",
            "昨收": 10.0,
            "今开": 10.45,
            "最新价": 10.60,
            "换手率": 12.0,
        }])
        assert m._evaluate(_make_stock(), spot, datetime.now(), False) is None

    def test_reject_turnover_out_of_range(self):
        m = self._monitor()
        spot = pd.DataFrame([{
            "代码": "000001",
            "昨收": 10.0,
            "今开": 10.45,
            "最新价": 10.80,
            "换手率": 3.0,
        }])
        assert m._evaluate(_make_stock(), spot, datetime.now(), False) is None


class TestHotSectorAnalyzer:
    def test_sector_bonus(self):
        analyzer = HotSectorAnalyzer()
        bonus = analyzer.calc_sector_bonus(["人工智能", "机器人"], 1500)
        assert bonus > 0

    def test_match_hot_sector(self):
        analyzer = HotSectorAnalyzer(require_hot_sector=True)
        analyzer._hot_sectors = ["人工智能"]
        analyzer._sector_stocks = {"人工智能": {"000001"}}
        analyzer._fund_flow_cache = {"000001": 800}
        passed, matched, flow, _ = analyzer.evaluate("000001", ["人工智能"])
        assert passed is True
        assert "人工智能" in matched
        assert flow == 800
