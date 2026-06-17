"""开盘监控：9:30高开3%-6%，涨幅超7%触发买点"""

from datetime import datetime, time

import akshare as ak
import pandas as pd
from loguru import logger

from src.hot_sector import HotSectorAnalyzer
from src.models import AuctionSignal, BuySignal, LimitUpStock
from src.utils import board_label


class OpeningMonitor:
    """
    开盘后买点监控。

    规则3：9:30成交高开3%-6%
    规则4：股价涨幅超过7%即为买点
    规则5：符合当前热点主线，主力资金大幅关注最佳
    """

    def __init__(
        self,
        open_gain_min: float = 3.0,
        open_gain_max: float = 6.0,
        buy_gain_threshold: float = 7.0,
        monitor_start: str = "09:30:00",
        monitor_end: str = "10:00:00",
        hot_sector: HotSectorAnalyzer | None = None,
    ):
        self.open_gain_min = open_gain_min
        self.open_gain_max = open_gain_max
        self.buy_gain_threshold = buy_gain_threshold
        self.monitor_start = self._parse_time(monitor_start)
        self.monitor_end = self._parse_time(monitor_end)
        self.hot_sector = hot_sector or HotSectorAnalyzer()

    def is_in_monitor_window(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        return self.monitor_start <= now.time() <= self.monitor_end

    def scan(
        self,
        candidates: list[LimitUpStock],
        auction_signals: list[AuctionSignal] | None = None,
        now: datetime | None = None,
    ) -> list[BuySignal]:
        """
        扫描开盘买点。

        优先处理通过竞价筛选（规则1-2）的标的，同时也扫描完整候选池。
        """
        now = now or datetime.now()
        if not self.is_in_monitor_window(now):
            logger.warning(
                f"当前 {now.strftime('%H:%M:%S')} 不在开盘监控窗口 "
                f"{self.monitor_start}-{self.monitor_end}"
            )

        self.hot_sector.refresh()
        spot_data = self._fetch_spot_snapshot()
        auction_codes = {s.code for s in (auction_signals or [])}

        # 竞价通过的优先，其余候选股次之
        ordered = self._order_candidates(candidates, auction_codes)
        signals: list[BuySignal] = []

        for stock in ordered:
            signal = self._evaluate(stock, spot_data, now, stock.code in auction_codes)
            if signal:
                signals.append(signal)

        signals.sort(key=lambda s: s.strength, reverse=True)
        logger.info(f"开盘买点扫描完成，触发 {len(signals)} 个买点")
        return signals

    def _evaluate(
        self,
        stock: LimitUpStock,
        spot_data: pd.DataFrame,
        now: datetime,
        passed_auction: bool,
    ) -> BuySignal | None:
        row = self._find_stock(spot_data, stock.code)
        if row is None:
            return None

        prev_close = float(row.get("昨收", row.get("pre_close", stock.close_price)) or stock.close_price)
        open_price = float(row.get("今开", row.get("open", 0)) or 0)
        current_price = float(row.get("最新价", row.get("close", 0)) or 0)

        if prev_close <= 0 or open_price <= 0 or current_price <= 0:
            return None

        open_gain_pct = (open_price / prev_close - 1) * 100
        current_gain_pct = (current_price / prev_close - 1) * 100

        reasons: list[str] = []

        if passed_auction:
            reasons.append("已通过竞价涨停报价筛选")

        # 规则3：高开3%-6%
        if not (self.open_gain_min <= open_gain_pct <= self.open_gain_max):
            return None
        reasons.append(f"高开 {open_gain_pct:.2f}%（{self.open_gain_min}%-{self.open_gain_max}%）")

        # 规则4：涨幅超过7%即为买点
        if current_gain_pct < self.buy_gain_threshold:
            return None
        reasons.append(f"涨幅 {current_gain_pct:.2f}% ≥ {self.buy_gain_threshold}% 触发买点")

        # 规则5：热点主线 + 主力资金
        stock_sectors = ([stock.sector] if stock.sector else []) + stock.concepts
        passed, matched, main_force, sector_reasons = self.hot_sector.evaluate(
            stock.code, stock_sectors
        )
        if not passed:
            return None
        reasons.extend(sector_reasons)

        strength = self._calc_strength(
            open_gain_pct, current_gain_pct, main_force, matched, stock.board_type.value
        )

        return BuySignal(
            code=stock.code,
            name=stock.name,
            board_type=stock.board_type,
            prev_close=prev_close,
            open_price=open_price,
            current_price=current_price,
            open_gain_pct=open_gain_pct,
            current_gain_pct=current_gain_pct,
            main_force_inflow=main_force,
            hot_sectors=self.hot_sector.hot_sectors[:5],
            matched_sectors=matched,
            signal_time=now,
            strength=strength,
            reasons=reasons,
        )

    def _calc_strength(
        self,
        open_gain: float,
        current_gain: float,
        main_force: float,
        matched_sectors: list[str],
        board_type: int,
    ) -> float:
        board_bonus = 10 if board_type == 1 else 5
        # 高开越接近区间中值(4.5%)越好
        open_score = 15 - abs(open_gain - 4.5) * 2
        open_score = max(open_score, 5)
        gain_score = min((current_gain - 7) * 3, 25)
        sector_score = self.hot_sector.calc_sector_bonus(matched_sectors, main_force)
        return round(board_bonus + open_score + gain_score + sector_score, 2)

    def _order_candidates(
        self, candidates: list[LimitUpStock], auction_codes: set[str]
    ) -> list[LimitUpStock]:
        priority = [c for c in candidates if c.code in auction_codes]
        rest = [c for c in candidates if c.code not in auction_codes]
        return priority + rest

    def _fetch_spot_snapshot(self) -> pd.DataFrame:
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
        return pd.DataFrame()

    def _find_stock(self, df: pd.DataFrame, code: str) -> pd.Series | None:
        if df.empty:
            return None
        code_col = "代码" if "代码" in df.columns else "code"
        if code_col not in df.columns:
            return None
        matched = df[df[code_col].astype(str).str.zfill(6) == code.zfill(6)]
        if matched.empty:
            return None
        return matched.iloc[0]

    @staticmethod
    def _parse_time(t: str) -> time:
        parts = [int(x) for x in t.split(":")]
        return time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)
