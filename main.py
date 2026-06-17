#!/usr/bin/env python3
"""竞价抓涨停 -- 决策先机 入口"""

import argparse
from datetime import datetime

from loguru import logger

from src.strategy import AuctionLimitUpStrategy


def main():
    parser = argparse.ArgumentParser(description="竞价抓涨停 -- 决策先机")
    parser.add_argument(
        "--date",
        help="目标交易日 YYYYMMDD（默认最近交易日）",
        default=None,
    )
    parser.add_argument(
        "--config",
        help="策略配置文件路径",
        default="config/strategy.yaml",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="仅筛选昨日涨停候选池，不扫描竞价",
    )
    parser.add_argument(
        "--mock-time",
        help="模拟当前时间 HH:MM:SS，用于测试竞价窗口",
        default=None,
    )
    args = parser.parse_args()

    logger.info("启动策略: 竞价抓涨停 -- 决策先机")

    strategy = AuctionLimitUpStrategy(config_path=args.config)

    if args.prepare_only:
        candidates = strategy.prepare(args.date)
        print(f"\n昨日涨停候选池: {len(candidates)} 只\n")
        for c in candidates:
            from src.utils import board_label
            print(
                f"  {c.name}({c.code}) | {board_label(c.board_type.value)} "
                f"| 收盘 {c.close_price:.2f} | 流通市值 {c.float_market_cap:.1f}亿"
            )
        return

    now = None
    if args.mock_time:
        today = datetime.now().date()
        h, m, s = [int(x) for x in args.mock_time.split(":")]
        now = datetime(today.year, today.month, today.day, h, m, s)

    signals = strategy.run_once(trade_date=args.date, now=now)
    print(strategy.format_signals(signals))


if __name__ == "__main__":
    main()
