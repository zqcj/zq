"""热点主线与主力资金分析"""

import akshare as ak
import pandas as pd
from loguru import logger

from src.utils import normalize_code


class HotSectorAnalyzer:
    """
    识别当前市场热点主线，评估主力资金关注度。

    规则5：符合当前热点主线，主力资金大幅关注最佳
    """

    def __init__(
        self,
        top_sector_count: int = 10,
        min_main_force_inflow: float = 500.0,
        require_hot_sector: bool = True,
    ):
        self.top_sector_count = top_sector_count
        self.min_main_force_inflow = min_main_force_inflow
        self.require_hot_sector = require_hot_sector
        self._hot_sectors: list[str] = []
        self._sector_stocks: dict[str, set[str]] = {}
        self._fund_flow_cache: dict[str, float] = {}

    def refresh(self) -> list[str]:
        """刷新热点板块列表"""
        self._hot_sectors = self._fetch_hot_sectors()
        self._sector_stocks = self._build_sector_stock_map(self._hot_sectors)
        self._fund_flow_cache = self._fetch_main_force_flow()
        logger.info(f"热点主线 Top{len(self._hot_sectors)}: {self._hot_sectors[:5]}...")
        return self._hot_sectors

    @property
    def hot_sectors(self) -> list[str]:
        if not self._hot_sectors:
            self.refresh()
        return self._hot_sectors

    def evaluate(
        self,
        code: str,
        stock_sectors: list[str] | None = None,
    ) -> tuple[bool, list[str], float, list[str]]:
        """
        评估个股是否符合热点主线及主力资金条件。

        Returns:
            (是否通过, 匹配的热点板块, 主力净流入万元, 原因列表)
        """
        if not self._hot_sectors:
            self.refresh()

        reasons: list[str] = []
        code = normalize_code(code)
        main_force = self._fund_flow_cache.get(code, 0.0)

        matched = self._match_hot_sectors(code, stock_sectors or [])
        is_hot = len(matched) > 0

        if is_hot:
            reasons.append(f"命中热点主线: {', '.join(matched)}")
        elif self.require_hot_sector:
            return False, matched, main_force, ["未命中当前热点主线"]

        if main_force >= self.min_main_force_inflow:
            reasons.append(f"主力净流入 {main_force:.0f} 万元")
        elif main_force > 0:
            reasons.append(f"主力净流入 {main_force:.0f} 万元（偏低）")
        else:
            reasons.append(f"主力净流出 {abs(main_force):.0f} 万元")

        passed = is_hot or not self.require_hot_sector
        if passed and main_force >= self.min_main_force_inflow:
            reasons.append("主力资金大幅关注")

        return passed, matched, main_force, reasons

    def calc_sector_bonus(self, matched_sectors: list[str], main_force: float) -> float:
        """热点与主力资金加分（0-30）"""
        sector_score = min(len(matched_sectors) * 8, 16)
        # 主力净流入越高加分越多，500万为基准
        fund_score = min(max(main_force, 0) / 500 * 7, 14)
        return round(sector_score + fund_score, 2)

    def _match_hot_sectors(self, code: str, stock_sectors: list[str]) -> list[str]:
        matched: list[str] = []
        for sector in self._hot_sectors:
            stocks = self._sector_stocks.get(sector, set())
            if code in stocks:
                matched.append(sector)
                continue
            for s in stock_sectors:
                if s and (s in sector or sector in s):
                    matched.append(sector)
                    break
        return matched

    def _fetch_hot_sectors(self) -> list[str]:
        """从板块资金流向获取热点主线"""
        sectors: list[str] = []
        try:
            df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
            if df is not None and not df.empty:
                name_col = "名称" if "名称" in df.columns else df.columns[1]
                sectors.extend(df.head(self.top_sector_count)[name_col].tolist())
        except Exception as e:
            logger.warning(f"行业资金流获取失败: {e}")

        try:
            df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="概念资金流")
            if df is not None and not df.empty:
                name_col = "名称" if "名称" in df.columns else df.columns[1]
                for name in df.head(self.top_sector_count)[name_col].tolist():
                    if name not in sectors:
                        sectors.append(name)
        except Exception as e:
            logger.warning(f"概念资金流获取失败: {e}")

        return sectors[: self.top_sector_count]

    def _build_sector_stock_map(self, sectors: list[str]) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = {}
        for sector in sectors:
            stocks = self._fetch_sector_stocks(sector)
            if stocks:
                mapping[sector] = stocks
        return mapping

    def _fetch_sector_stocks(self, sector: str) -> set[str]:
        for fetcher in (
            lambda: ak.stock_board_industry_cons_em(symbol=sector),
            lambda: ak.stock_board_concept_cons_em(symbol=sector),
        ):
            try:
                df = fetcher()
                if df is not None and not df.empty:
                    code_col = "代码" if "代码" in df.columns else "code"
                    return {normalize_code(str(c)) for c in df[code_col]}
            except Exception:
                continue
        return set()

    def _fetch_main_force_flow(self) -> dict[str, float]:
        """获取个股主力净流入（万元）"""
        cache: dict[str, float] = {}
        try:
            df = ak.stock_individual_fund_flow_rank(indicator="今日")
            if df is None or df.empty:
                return cache
            code_col = "代码" if "代码" in df.columns else df.columns[1]
            flow_col = self._find_flow_column(df)
            for _, row in df.iterrows():
                code = normalize_code(str(row[code_col]))
                cache[code] = float(row[flow_col] or 0)
        except Exception as e:
            logger.warning(f"主力资金流向获取失败: {e}")
        return cache

    @staticmethod
    def _find_flow_column(df: pd.DataFrame) -> str:
        for col in df.columns:
            if "主力净流入" in str(col):
                return col
        return df.columns[-1]
