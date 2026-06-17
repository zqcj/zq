"""竞价抓涨停 -- 决策先机 策略引擎"""

from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger

from src.auction_monitor import AuctionMonitor
from src.hot_sector import HotSectorAnalyzer
from src.models import AuctionSignal, BuySignal, LimitUpStock
from src.opening_monitor import OpeningMonitor
from src.screener import LimitUpScreener
from src.utils import board_label


class AuctionLimitUpStrategy:
    """
    竞价抓涨停 -- 决策先机

    策略规则：
    1. 昨日出现涨停，首板二板都可
    2. 集合竞价 9:20 之前出现涨停板报价
    3. 9:30 成交高开 3%-6%
    4. 股价涨幅超过 7% 即为买点
    5. 符合当前热点主线，主力资金大幅关注最佳
    """

    def __init__(self, config_path: str | Path | None = None):
        config_path = Path(config_path or "config/strategy.yaml")
        with open(config_path, encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        screener_cfg = self.config.get("screener", {})
        auction_cfg = self.config.get("auction", {})
        opening_cfg = self.config.get("opening", {})
        hot_cfg = self.config.get("hot_sector", {})

        self.screener = LimitUpScreener(
            allowed_boards=screener_cfg.get("allowed_boards", [1, 2]),
            exclude_st=screener_cfg.get("exclude_st", True),
            min_float_market_cap=screener_cfg.get("min_float_market_cap", 10),
            max_float_market_cap=screener_cfg.get("max_float_market_cap", 500),
            turnover_min=screener_cfg.get("turnover_min", 8.0),
            turnover_max=screener_cfg.get("turnover_max", 20.0),
        )
        self.monitor = AuctionMonitor(
            start_time=auction_cfg.get("start_time", "09:15:00"),
            end_time=auction_cfg.get("end_time", "09:20:00"),
            limit_up_tolerance=auction_cfg.get("limit_up_tolerance", 0.998),
            min_auction_gain_pct=auction_cfg.get("min_auction_gain_pct", 9.0),
            min_auction_volume_ratio=auction_cfg.get("min_auction_volume_ratio", 0.01),
        )
        self.hot_sector = HotSectorAnalyzer(
            top_sector_count=hot_cfg.get("top_sector_count", 10),
            min_main_force_inflow=hot_cfg.get("min_main_force_inflow", 500),
            require_hot_sector=hot_cfg.get("require_hot_sector", True),
        )
        self.opening = OpeningMonitor(
            open_gain_min=opening_cfg.get("open_gain_min", 3.0),
            open_gain_max=opening_cfg.get("open_gain_max", 6.0),
            buy_gain_threshold=opening_cfg.get("buy_gain_threshold", 7.0),
            monitor_start=opening_cfg.get("monitor_start", "09:30:00"),
            monitor_end=opening_cfg.get("monitor_end", "10:00:00"),
            turnover_min=opening_cfg.get("turnover_min", 8.0),
            turnover_max=opening_cfg.get("turnover_max", 20.0),
            hot_sector=self.hot_sector,
        )

        self._candidates: list[LimitUpStock] = []
        self._auction_signals: list[AuctionSignal] = []

    def prepare(self, trade_date: str | None = None) -> list[LimitUpStock]:
        """盘前准备：筛选昨日涨停候选池"""
        self._candidates = self.screener.screen(trade_date)
        return self._candidates

    def run_auction(self, now: datetime | None = None) -> list[AuctionSignal]:
        """执行规则1-2：竞价窗口扫描"""
        if not self._candidates:
            self.prepare()
        self._auction_signals = self.monitor.scan(self._candidates, now)
        return self._auction_signals

    def run_opening(self, now: datetime | None = None) -> list[BuySignal]:
        """执行规则3-5：开盘买点扫描"""
        if not self._candidates:
            self.prepare()
        if not self._auction_signals:
            self._auction_signals = self.monitor.scan(self._candidates, now)
        return self.opening.scan(self._candidates, self._auction_signals, now)

    def run(self, now: datetime | None = None) -> list[BuySignal]:
        """执行完整策略流水线"""
        auction = self.run_auction(now)
        logger.info(f"竞价信号 {len(auction)} 个，进入开盘买点扫描")
        return self.run_opening(now)

    def run_once(self, trade_date: str | None = None, now: datetime | None = None) -> list[BuySignal]:
        """一键运行：筛选 + 竞价 + 开盘买点"""
        self.prepare(trade_date)
        return self.run(now)

    def format_auction_signals(self, signals: list[AuctionSignal]) -> str:
        if not signals:
            return "暂无符合条件的竞价涨停信号"
        lines = ["=" * 60, "  竞价信号（规则1-2）", "=" * 60]
        for i, sig in enumerate(signals, 1):
            lines.extend([
                f"\n[{i}] {sig.name}({sig.code}) | {board_label(sig.board_type.value)}",
                f"    竞价价: {sig.auction_price:.2f}  涨停价: {sig.limit_up_price:.2f}",
                f"    竞价涨幅: {sig.auction_gain_pct:.2f}%  量比: {sig.volume_ratio:.2%}",
                f"    强度: {sig.strength:.1f}  时间: {sig.signal_time.strftime('%H:%M:%S')}",
            ])
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def format_buy_signals(self, signals: list[BuySignal]) -> str:
        if not signals:
            return "暂无符合条件的买点信号"
        lines = [
            "=" * 60,
            "  竞价抓涨停 -- 决策先机 | 买点信号（规则1-5）",
            "=" * 60,
        ]
        for i, sig in enumerate(signals, 1):
            lines.extend([
                f"\n[{i}] {sig.name}({sig.code}) | {board_label(sig.board_type.value)}",
                f"    昨收: {sig.prev_close:.2f}  开盘: {sig.open_price:.2f}  现价: {sig.current_price:.2f}",
                f"    高开: {sig.open_gain_pct:.2f}%  涨幅: {sig.current_gain_pct:.2f}%  换手: {sig.turnover_rate:.2f}%",
                f"    主力净流入: {sig.main_force_inflow:.0f} 万元",
                f"    热点主线: {', '.join(sig.matched_sectors) or '无'}",
                f"    强度: {sig.strength:.1f}  时间: {sig.signal_time.strftime('%H:%M:%S')}",
                f"    依据: {'; '.join(sig.reasons)}",
            ])
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

    def format_signals(self, signals: list[BuySignal]) -> str:
        return self.format_buy_signals(signals)
