"""竞价抓涨停 -- 决策先机 策略引擎"""

from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger

from src.auction_monitor import AuctionMonitor
from src.models import AuctionSignal, LimitUpStock
from src.screener import LimitUpScreener
from src.utils import board_label


class AuctionLimitUpStrategy:
    """
    竞价抓涨停 -- 决策先机

    策略规则：
    1. 昨日出现涨停，首板二板都可
    2. 集合竞价 9:20 之前出现涨停板报价
    """

    def __init__(self, config_path: str | Path | None = None):
        config_path = Path(config_path or "config/strategy.yaml")
        with open(config_path, encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        screener_cfg = self.config.get("screener", {})
        auction_cfg = self.config.get("auction", {})

        self.screener = LimitUpScreener(
            allowed_boards=screener_cfg.get("allowed_boards", [1, 2]),
            exclude_st=screener_cfg.get("exclude_st", True),
            min_float_market_cap=screener_cfg.get("min_float_market_cap", 10),
            max_float_market_cap=screener_cfg.get("max_float_market_cap", 500),
        )
        self.monitor = AuctionMonitor(
            start_time=auction_cfg.get("start_time", "09:15:00"),
            end_time=auction_cfg.get("end_time", "09:20:00"),
            limit_up_tolerance=auction_cfg.get("limit_up_tolerance", 0.998),
            min_auction_gain_pct=auction_cfg.get("min_auction_gain_pct", 9.0),
            min_auction_volume_ratio=auction_cfg.get("min_auction_volume_ratio", 0.01),
        )

        self._candidates: list[LimitUpStock] = []

    def prepare(self, trade_date: str | None = None) -> list[LimitUpStock]:
        """盘前准备：筛选昨日涨停候选池"""
        self._candidates = self.screener.screen(trade_date)
        return self._candidates

    def run(self, now: datetime | None = None) -> list[AuctionSignal]:
        """执行策略：在竞价窗口扫描信号"""
        if not self._candidates:
            logger.info("候选池为空，先执行 prepare()")
            self.prepare()

        return self.monitor.scan(self._candidates, now)

    def run_once(self, trade_date: str | None = None, now: datetime | None = None) -> list[AuctionSignal]:
        """一键运行：筛选 + 扫描"""
        self.prepare(trade_date)
        return self.run(now)

    def format_signals(self, signals: list[AuctionSignal]) -> str:
        """格式化输出信号"""
        if not signals:
            return "暂无符合条件的竞价涨停信号"

        lines = [
            "=" * 60,
            "  竞价抓涨停 -- 决策先机 | 信号列表",
            "=" * 60,
        ]
        for i, sig in enumerate(signals, 1):
            lines.extend([
                f"\n[{i}] {sig.name}({sig.code}) | {board_label(sig.board_type.value)}",
                f"    竞价价: {sig.auction_price:.2f}  涨停价: {sig.limit_up_price:.2f}",
                f"    竞价涨幅: {sig.auction_gain_pct:.2f}%  量比: {sig.volume_ratio:.2%}",
                f"    强度: {sig.strength:.1f}  时间: {sig.signal_time.strftime('%H:%M:%S')}",
                f"    依据: {'; '.join(sig.reasons)}",
            ])
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
