#!/usr/bin/env python3
"""星火燎原选股筛选 — 全市场扫描入口"""

import argparse
from datetime import datetime

from loguru import logger

from src.xinghuo_screener import XinghuoScreener


def main():
    parser = argparse.ArgumentParser(description="星火燎原选股筛选")
    parser.add_argument("--date", help="目标交易日 YYYYMMDD", default=None)
    parser.add_argument("--csv", help="导出结果到 CSV 文件", default=None)
    args = parser.parse_args()

    trade_date = args.date
    if trade_date is None:
        trade_date = datetime.now().strftime("%Y%m%d")

    logger.info("=" * 60)
    logger.info("星火燎原选股筛选")
    logger.info("=" * 60)
    logger.info("筛选条件：")
    logger.info("  1. 底部起涨 ≤ 30%（3个月内）")
    logger.info("  2. 半年内试盘线 ≥ 2次，含三倍量试盘线")
    logger.info("  3. 今日拉升型涨停（换手8~20%，温和/倍量，炸板回封）")
    logger.info("  4. 股价站上60日均线")
    logger.info("  5. 次日突破今日涨停收盘价介入")
    logger.info("=" * 60)

    screener = XinghuoScreener()
    results = screener.screen(trade_date)

    print(f"\n交易日: {trade_date}")
    print(f"符合条件: {len(results)} 只\n")

    if not results:
        print("今日暂无符合星火燎原形态的股票。")
        print("\n说明：策略要求今日出现拉升型涨停板，因此候选池从全市场涨停股中筛选。")
        return

    print(f"{'代码':<8} {'名称':<10} {'收盘价':>8} {'换手率':>8} {'炸板':>4} {'量比':>6} {'底部涨幅':>8} {'试盘线':>6} {'60MA':>8} {'介入价':>8} {'行业'}")
    print("-" * 110)

    rows = []
    for r in results:
        print(
            f"{r.code:<8} {r.name:<10} {r.close_price:>8.2f} {r.turnover_rate:>7.2f}% "
            f"{r.zhaban_count:>4} {r.vol_ratio:>6.2f} {r.rise_from_bottom_pct:>7.1f}% "
            f"{r.trial_line_count:>6} {r.ma60:>8.2f} {r.entry_price:>8.2f} {r.sector}"
        )
        rows.append(
            {
                "代码": r.code,
                "名称": r.name,
                "收盘价": r.close_price,
                "换手率%": r.turnover_rate,
                "炸板次数": r.zhaban_count,
                "量比": r.vol_ratio,
                "底部涨幅%": r.rise_from_bottom_pct,
                "试盘线次数": r.trial_line_count,
                "三倍量试盘": r.triple_trial_count,
                "60MA": r.ma60,
                "介入价": r.entry_price,
                "行业": r.sector,
            }
        )

    print("\n【操作提示】规则5：次日股价突破上表「介入价」（今日涨停收盘价）时可考虑介入。")

    if args.csv:
        import pandas as pd

        pd.DataFrame(rows).to_csv(args.csv, index=False, encoding="utf-8-sig")
        print(f"\n结果已导出: {args.csv}")


if __name__ == "__main__":
    main()
