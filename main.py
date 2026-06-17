#!/usr/bin/env python3
"""竞价抓涨停 -- 决策先机 入口"""

import argparse
from datetime import datetime

from loguru import logger

from src.strategy import AuctionLimitUpStrategy
from src.utils import board_label


def main():
    parser = argparse.ArgumentParser(description="竞价抓涨停 -- 决策先机")
    parser.add_argument("--date", help="目标交易日 YYYYMMDD", default=None)
    parser.add_argument("--config", default="config/strategy.yaml")
    parser.add_argument("--prepare-only", action="store_true", help="仅筛选昨日涨停候选池")
    parser.add_argument("--auction-only", action="store_true", help="仅运行竞价扫描（规则1-2）")
    parser.add_argument("--mock-time", help="模拟当前时间 HH:MM:SS", default=None)
    args = parser.parse_args()

    logger.info("启动策略: 竞价抓涨停 -- 决策先机")

    strategy = AuctionLimitUpStrategy(config_path=args.config)
    now = _parse_mock_time(args.mock_time)

    if args.prepare_only:
        candidates = strategy.prepare(args.date)
        print(f"\n昨日涨停候选池: {len(candidates)} 只\n")
        for c in candidates:
            sector_info = f" | {c.sector}" if c.sector else ""
            print(
                f"  {c.name}({c.code}) | {board_label(c.board_type.value)}"
                f" | 收盘 {c.close_price:.2f}{sector_info}"
            )
        return

    strategy.prepare(args.date)

    if args.auction_only:
        signals = strategy.run_auction(now)
        print(strategy.format_auction_signals(signals))
        return

    buy_signals = strategy.run(now)
    auction_signals = strategy._auction_signals
    if auction_signals:
        print(strategy.format_auction_signals(auction_signals))
        print()
    print(strategy.format_buy_signals(buy_signals))


def _parse_mock_time(mock_time: str | None) -> datetime | None:
    if not mock_time:
        return None
    today = datetime.now().date()
    h, m, s = [int(x) for x in mock_time.split(":")]
    return datetime(today.year, today.month, today.day, h, m, s)


if __name__ == "__main__":
    main()
