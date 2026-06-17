"""
星火燎原选股筛选器

条件：
1. 底部起涨不超过30%（3个月内）
2. 半年内出现两次以上试盘线，其中一次为三倍量试盘线
3. 今日出现拉升型涨停板（换手8%~20%，量能温和/倍量非爆量，炸板回封）
4. 股价位于60MA上方运行
5. 次日股价超过今日涨停板收盘价介入（输出参考介入价）
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd
from loguru import logger

from src.utils import is_st_stock, normalize_code


@dataclass
class XinghuoResult:
    """星火燎原筛选结果"""

    code: str
    name: str
    close_price: float
    limit_up_price: float
    turnover_rate: float
    zhaban_count: int
    vol_ratio: float
    rise_from_bottom_pct: float
    trial_line_count: int
    triple_trial_count: int
    ma60: float
    above_ma60: bool
    sector: str
    entry_price: float  # 规则5：次日突破此价介入
    reasons: list[str] = field(default_factory=list)


class XinghuoScreener:
    """星火燎原形态筛选"""

    def __init__(
        self,
        turnover_min: float = 8.0,
        turnover_max: float = 20.0,
        max_rise_from_bottom_pct: float = 30.0,
        bottom_lookback_days: int = 63,
        trial_lookback_days: int = 126,
        min_trial_lines: int = 2,
        vol_ratio_min: float = 1.0,
        vol_ratio_max: float = 3.0,
        request_delay: float = 0.15,
        max_retries: int = 3,
    ):
        self.turnover_min = turnover_min
        self.turnover_max = turnover_max
        self.max_rise_from_bottom_pct = max_rise_from_bottom_pct
        self.bottom_lookback_days = bottom_lookback_days
        self.trial_lookback_days = trial_lookback_days
        self.min_trial_lines = min_trial_lines
        self.vol_ratio_min = vol_ratio_min
        self.vol_ratio_max = vol_ratio_max
        self.request_delay = request_delay
        self.max_retries = max_retries
        self._daily_cache: dict[str, pd.DataFrame] = {}

    def screen(self, trade_date: str | None = None) -> list[XinghuoResult]:
        if trade_date is None:
            trade_date = self._latest_trade_date()

        logger.info(f"星火燎原筛选 — 交易日 {trade_date}")

        limit_up_df = self._fetch_limit_up_pool(trade_date)
        if limit_up_df.empty:
            logger.warning("今日无涨停数据")
            return []

        logger.info(f"全市场涨停 {len(limit_up_df)} 只，开始逐只技术形态校验…")

        results: list[XinghuoResult] = []
        for _, row in limit_up_df.iterrows():
            result = self._evaluate_row(row, trade_date)
            if result is not None:
                results.append(result)

        logger.info(f"星火燎原筛选完成，符合条件 {len(results)} 只")
        return results

    def _evaluate_row(self, row: pd.Series, trade_date: str) -> XinghuoResult | None:
        code = normalize_code(str(row.get("代码", "")))
        name = str(row.get("名称", ""))
        if not code or not name or is_st_stock(name):
            return None

        turnover = float(row.get("换手率", 0) or 0)
        zhaban = int(row.get("炸板次数", 0) or 0)
        close_price = float(row.get("最新价", 0) or 0)
        sector = str(row.get("所属行业", "") or "")

        reasons: list[str] = []

        # 规则3a：拉升型涨停 — 换手率 8%~20%
        if not (self.turnover_min <= turnover <= self.turnover_max):
            return None
        reasons.append(f"换手{turnover:.2f}%")

        # 规则3c：炸板回封
        if zhaban <= 0:
            return None
        reasons.append(f"炸板回封{zhaban}次")

        daily = self._fetch_daily(code, trade_date)
        if daily is None or len(daily) < 70:
            return None

        daily = daily.copy()
        daily["date"] = pd.to_datetime(daily["date"])
        daily = daily.sort_values("date").reset_index(drop=True)

        # 规则3b：量能温和放大或倍量，非爆大量
        vol_ratio = self._calc_vol_ratio(daily)
        if not (self.vol_ratio_min <= vol_ratio <= self.vol_ratio_max):
            return None
        reasons.append(f"量比{vol_ratio:.2f}")

        # 规则4：60MA上方
        daily["ma60"] = daily["close"].rolling(60).mean()
        last = daily.iloc[-1]
        ma60 = float(last["ma60"])
        if pd.isna(ma60) or last["close"] <= ma60:
            return None
        reasons.append(f"站上60MA({ma60:.2f})")

        # 规则1：底部起涨不超过30%（3个月）
        rise_pct = self._calc_rise_from_bottom(daily)
        if rise_pct > self.max_rise_from_bottom_pct:
            return None
        reasons.append(f"底部涨幅{rise_pct:.1f}%")

        # 规则2：半年内试盘线 >= 2，含三倍量试盘线
        trials = self._detect_trial_lines(daily)
        cutoff = daily["date"].max() - pd.Timedelta(days=180)
        recent_trials = [t for t in trials if t["date"] >= cutoff]
        triple_trials = [t for t in recent_trials if t["triple"]]

        if len(recent_trials) < self.min_trial_lines:
            return None
        if len(triple_trials) < 1:
            return None
        reasons.append(f"试盘线{len(recent_trials)}次(含{len(triple_trials)}次三倍量)")

        return XinghuoResult(
            code=code,
            name=name,
            close_price=close_price,
            limit_up_price=close_price,
            turnover_rate=turnover,
            zhaban_count=zhaban,
            vol_ratio=vol_ratio,
            rise_from_bottom_pct=rise_pct,
            trial_line_count=len(recent_trials),
            triple_trial_count=len(triple_trials),
            ma60=ma60,
            above_ma60=True,
            sector=sector,
            entry_price=close_price,
            reasons=reasons,
        )

    def _calc_vol_ratio(self, daily: pd.DataFrame) -> float:
        """今日成交量 / 前5日均量"""
        if len(daily) < 7:
            return 0.0
        today_vol = float(daily.iloc[-1]["volume"])
        prev_avg = float(daily.iloc[-6:-1]["volume"].mean())
        if prev_avg <= 0:
            return 0.0
        return today_vol / prev_avg

    def _calc_rise_from_bottom(self, daily: pd.DataFrame) -> float:
        """从近3个月最低点算起涨幅"""
        window = daily.tail(self.bottom_lookback_days)
        min_low = float(window["low"].min())
        close = float(daily.iloc[-1]["close"])
        if min_low <= 0:
            return 999.0
        return (close - min_low) / min_low * 100

    def _detect_trial_lines(self, daily: pd.DataFrame) -> list[dict]:
        """
        试盘线判定：
        - 上影线 >= 2倍实体
        - 上影线占收盘价 >= 2%
        三倍量试盘线：当日成交量 >= 3倍前5日均量
        """
        trials: list[dict] = []
        for i in range(5, len(daily)):
            row = daily.iloc[i]
            o, h, c = float(row["open"]), float(row["high"]), float(row["close"])
            body = max(abs(c - o), 0.01)
            upper = h - max(o, c)
            if upper < 2 * body or upper / c < 0.02:
                continue
            vol_ma5 = float(daily.iloc[i - 5 : i]["volume"].mean())
            vol = float(row["volume"])
            vol_ratio = vol / vol_ma5 if vol_ma5 > 0 else 0
            trials.append(
                {
                    "date": row["date"],
                    "vol_ratio": vol_ratio,
                    "triple": vol_ratio >= 3.0,
                }
            )
        return trials

    def _fetch_daily(self, code: str, end_date: str) -> pd.DataFrame | None:
        if code in self._daily_cache:
            return self._daily_cache[code]

        prefix = "sz" if code.startswith(("0", "3")) else "sh"
        symbol = f"{prefix}{code}"
        start = (
            datetime.strptime(end_date, "%Y%m%d") - timedelta(days=280)
        ).strftime("%Y%m%d")

        for attempt in range(self.max_retries):
            try:
                time.sleep(self.request_delay)
                df = ak.stock_zh_a_daily(
                    symbol=symbol,
                    start_date=start,
                    end_date=end_date,
                    adjust="qfq",
                )
                if df is not None and not df.empty:
                    self._daily_cache[code] = df
                    return df
            except Exception as e:
                logger.debug(f"{code} 日线获取失败({attempt + 1}): {e}")
                time.sleep(1.5 * (attempt + 1))

        return None

    def _fetch_limit_up_pool(self, trade_date: str) -> pd.DataFrame:
        for attempt in range(self.max_retries):
            try:
                df = ak.stock_zt_pool_em(date=trade_date)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"涨停池获取失败({attempt + 1}): {e}")
                time.sleep(2)
        return pd.DataFrame()

    def _latest_trade_date(self) -> str:
        today = datetime.now()
        for offset in range(0, 10):
            candidate = (today - timedelta(days=offset)).strftime("%Y%m%d")
            try:
                df = ak.stock_zt_pool_em(date=candidate)
                if df is not None and not df.empty:
                    return candidate
            except Exception:
                continue
        return (today - timedelta(days=1)).strftime("%Y%m%d")
