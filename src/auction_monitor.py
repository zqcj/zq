"""集合竞价监控：9:20前涨停价报价检测"""

from datetime import datetime, time

import akshare as ak
import pandas as pd
from loguru import logger

from src.models import AuctionSignal, LimitUpStock
from src.utils import board_label, calc_limit_up_price


class AuctionMonitor:
    """
    监控集合竞价阶段是否出现涨停价报价。

    A股集合竞价：
    - 9:15-9:20：可挂单可撤单（决策先机窗口）
    - 9:20-9:25：可挂单不可撤单
    - 9:25：撮合出开盘价
    """

    def __init__(
        self,
        start_time: str = "09:15:00",
        end_time: str = "09:20:00",
        limit_up_tolerance: float = 0.998,
        min_auction_gain_pct: float = 9.0,
        min_auction_volume_ratio: float = 0.01,
    ):
        self.start_time = self._parse_time(start_time)
        self.end_time = self._parse_time(end_time)
        self.limit_up_tolerance = limit_up_tolerance
        self.min_auction_gain_pct = min_auction_gain_pct
        self.min_auction_volume_ratio = min_auction_volume_ratio

    def is_in_monitor_window(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        current = now.time()
        return self.start_time <= current <= self.end_time

    def scan(
        self,
        candidates: list[LimitUpStock],
        now: datetime | None = None,
    ) -> list[AuctionSignal]:
        """
        扫描候选股集合竞价报价，返回满足条件的信号。

        核心条件：9:20前出现涨停价报价
        """
        now = now or datetime.now()
        if not self.is_in_monitor_window(now):
            logger.warning(
                f"当前 {now.strftime('%H:%M:%S')} 不在监控窗口 "
                f"{self.start_time}-{self.end_time}"
            )

        signals: list[AuctionSignal] = []
        auction_data = self._fetch_auction_snapshot()

        for stock in candidates:
            signal = self._evaluate(stock, auction_data, now)
            if signal:
                signals.append(signal)

        signals.sort(key=lambda s: s.strength, reverse=True)
        logger.info(f"竞价扫描完成，触发 {len(signals)} 个信号")
        return signals

    def _evaluate(
        self,
        stock: LimitUpStock,
        auction_data: pd.DataFrame,
        now: datetime,
    ) -> AuctionSignal | None:
        row = self._find_stock(auction_data, stock.code)
        if row is None:
            return None

        auction_price = float(row.get("竞价价格", row.get("最新价", 0)) or 0)
        auction_volume = float(row.get("竞价成交量", row.get("成交量", 0)) or 0)
        prev_close = stock.close_price

        if auction_price <= 0 or prev_close <= 0:
            return None

        limit_up_price = stock.limit_up_price or calc_limit_up_price(
            prev_close, stock.code, stock.name
        )
        auction_gain_pct = (auction_price / prev_close - 1) * 100
        volume_ratio = auction_volume / stock.volume if stock.volume > 0 else 0

        reasons: list[str] = []
        has_limit_up_quote = auction_price >= limit_up_price * self.limit_up_tolerance

        if not has_limit_up_quote:
            return None
        reasons.append(f"竞价报价 {auction_price:.2f} 触及涨停价 {limit_up_price:.2f}")

        if auction_gain_pct < self.min_auction_gain_pct:
            return None
        reasons.append(f"竞价涨幅 {auction_gain_pct:.2f}%")

        if volume_ratio < self.min_auction_volume_ratio:
            return None
        reasons.append(f"竞价量比 {volume_ratio:.2%}")

        strength = self._calc_strength(
            auction_gain_pct, volume_ratio, stock.board_type.value
        )

        return AuctionSignal(
            code=stock.code,
            name=stock.name,
            board_type=stock.board_type,
            auction_price=auction_price,
            limit_up_price=limit_up_price,
            auction_gain_pct=auction_gain_pct,
            auction_volume=auction_volume,
            volume_ratio=volume_ratio,
            signal_time=now,
            strength=strength,
            reasons=reasons,
        )

    def _calc_strength(
        self, gain_pct: float, volume_ratio: float, board_type: int
    ) -> float:
        """
        信号强度评分（0-100）。

        首板权重略高于二板（博弈空间更大），涨幅和量比越高分越高。
        """
        board_bonus = 10 if board_type == 1 else 5
        gain_score = min(gain_pct / 10 * 40, 40)
        vol_score = min(volume_ratio * 1000, 50)
        return round(board_bonus + gain_score + vol_score, 2)

    def _fetch_auction_snapshot(self) -> pd.DataFrame:
        """获取实时集合竞价行情快照"""
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.error(f"获取竞价行情失败: {e}")
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
