"""昨日涨停筛选器：首板 / 二板"""

from datetime import datetime, timedelta

import akshare as ak
import pandas as pd
from loguru import logger

from src.models import BoardType, LimitUpStock
from src.utils import board_label, is_st_stock, is_turnover_in_range, normalize_code


class LimitUpScreener:
    """
    筛选昨日涨停股，区分首板与二板。

    规则：
    - 首板：昨日涨停，且前日未涨停
    - 二板：昨日涨停，且前日也涨停（连续2天）
    """

    def __init__(
        self,
        allowed_boards: list[int] | None = None,
        exclude_st: bool = True,
        min_float_market_cap: float = 10.0,
        max_float_market_cap: float = 500.0,
        turnover_min: float = 8.0,
        turnover_max: float = 20.0,
    ):
        self.allowed_boards = allowed_boards or [1, 2]
        self.exclude_st = exclude_st
        self.min_float_market_cap = min_float_market_cap
        self.max_float_market_cap = max_float_market_cap
        self.turnover_min = turnover_min
        self.turnover_max = turnover_max

    def screen(self, trade_date: str | None = None) -> list[LimitUpStock]:
        """
        获取昨日涨停候选池。

        Args:
            trade_date: 目标交易日 YYYYMMDD，默认取最近交易日
        """
        if trade_date is None:
            trade_date = self._latest_trade_date()

        logger.info(f"筛选 {trade_date} 涨停股，允许板位: {[board_label(b) for b in self.allowed_boards]}")

        limit_up_df = self._fetch_limit_up_pool(trade_date)
        if limit_up_df.empty:
            logger.warning(f"{trade_date} 无涨停数据")
            return []

        results: list[LimitUpStock] = []
        for _, row in limit_up_df.iterrows():
            stock = self._parse_row(row, trade_date)
            if stock is None:
                continue
            if stock.board_type.value not in self.allowed_boards:
                continue
            if self.exclude_st and is_st_stock(stock.name):
                continue
            if not (self.min_float_market_cap <= stock.float_market_cap <= self.max_float_market_cap):
                continue
            if not is_turnover_in_range(stock.turnover_rate, self.turnover_min, self.turnover_max):
                continue
            results.append(stock)

        logger.info(f"筛选完成，共 {len(results)} 只候选股")
        return results

    def _fetch_limit_up_pool(self, trade_date: str) -> pd.DataFrame:
        """从涨停池接口获取数据，附带连板数"""
        try:
            df = ak.stock_zt_pool_em(date=trade_date)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.warning(f"涨停池接口失败: {e}")

        # 回退：从行情数据自行判断
        return self._fallback_limit_up_scan(trade_date)

    def _parse_row(self, row: pd.Series, trade_date: str) -> LimitUpStock | None:
        code = normalize_code(str(row.get("代码", row.get("code", ""))))
        name = str(row.get("名称", row.get("name", "")))
        if not code or not name:
            return None

        consecutive = int(row.get("连板数", row.get("consecutive", 1)) or 1)
        board_type = self._resolve_board_type(consecutive)

        close_price = float(row.get("最新价", row.get("close", 0)) or 0)
        limit_up_price = float(row.get("涨停价", close_price) or close_price)
        volume = float(row.get("成交量", row.get("volume", 0)) or 0)

        # 流通市值：接口单位可能为元或亿元
        raw_cap = float(row.get("流通市值", row.get("float_market_cap", 0)) or 0)
        float_cap = raw_cap / 1e8 if raw_cap > 1e6 else raw_cap

        sector = str(row.get("所属行业", row.get("sector", "")) or "")
        concept_raw = str(row.get("所属概念", row.get("concepts", "")) or "")
        concepts = [c.strip() for c in concept_raw.split(",") if c.strip()]
        turnover = float(row.get("换手率", row.get("turnover", 0)) or 0)

        return LimitUpStock(
            code=code,
            name=name,
            board_type=board_type,
            close_price=close_price,
            limit_up_price=limit_up_price,
            volume=volume,
            float_market_cap=float_cap,
            consecutive_days=consecutive,
            trade_date=trade_date,
            sector=sector,
            concepts=concepts,
            turnover_rate=turnover,
        )

    def _resolve_board_type(self, consecutive: int) -> BoardType:
        if consecutive >= 2:
            return BoardType.SECOND
        return BoardType.FIRST

    def _fallback_limit_up_scan(self, trade_date: str) -> pd.DataFrame:
        """接口不可用时的备用扫描（返回空表，由调用方处理）"""
        logger.error("涨停池数据不可用，请检查网络或 akshare 版本")
        return pd.DataFrame()

    def _latest_trade_date(self) -> str:
        """获取最近一个交易日"""
        today = datetime.now()
        for offset in range(1, 10):
            candidate = (today - timedelta(days=offset)).strftime("%Y%m%d")
            try:
                df = ak.stock_zt_pool_em(date=candidate)
                if df is not None and not df.empty:
                    return candidate
            except Exception:
                continue
        return (today - timedelta(days=1)).strftime("%Y%m%d")
