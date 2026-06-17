"""涨停价与连板计算工具"""

import re


def is_st_stock(name: str) -> bool:
    return "ST" in name.upper()


def calc_limit_up_price(prev_close: float, code: str, name: str) -> float:
    """
    计算涨停价（A股四舍五入到分）。

    - 主板/中小板：10%
    - ST：5%
    - 创业板(300)/科创板(688)：20%
    """
    if prev_close <= 0:
        return 0.0

    if is_st_stock(name):
        ratio = 1.05
    elif code.startswith(("300", "688")):
        ratio = 1.20
    else:
        ratio = 1.10

    return round(prev_close * ratio, 2)


def is_limit_up(close: float, prev_close: float, code: str, name: str) -> bool:
    """判断是否涨停收盘"""
    if prev_close <= 0:
        return False
    limit_price = calc_limit_up_price(prev_close, code, name)
    return close >= limit_price * 0.998


def normalize_code(code: str) -> str:
    """统一股票代码为6位数字"""
    digits = re.sub(r"\D", "", code)
    return digits.zfill(6)[-6:]


def board_label(board_type: int) -> str:
    return {1: "首板", 2: "二板"}.get(board_type, f"{board_type}连板")


def is_turnover_in_range(turnover: float, min_pct: float = 8.0, max_pct: float = 20.0) -> bool:
    """换手率是否在指定区间（拉升型涨停板特征）"""
    return min_pct <= turnover <= max_pct
