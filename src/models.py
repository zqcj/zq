from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum


class BoardType(IntEnum):
    """连板类型"""

    FIRST = 1  # 首板
    SECOND = 2  # 二板


@dataclass
class LimitUpStock:
    """昨日涨停候选股"""

    code: str
    name: str
    board_type: BoardType
    close_price: float
    limit_up_price: float
    volume: float
    float_market_cap: float  # 亿元
    consecutive_days: int
    trade_date: str
    sector: str = ""
    concepts: list[str] = field(default_factory=list)


@dataclass
class AuctionSignal:
    """集合竞价信号（规则1-2）"""

    code: str
    name: str
    board_type: BoardType
    auction_price: float
    limit_up_price: float
    auction_gain_pct: float
    auction_volume: float
    volume_ratio: float
    signal_time: datetime
    strength: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass
class BuySignal:
    """完整买点信号（规则1-5）"""

    code: str
    name: str
    board_type: BoardType
    prev_close: float
    open_price: float
    current_price: float
    open_gain_pct: float
    current_gain_pct: float
    main_force_inflow: float  # 主力净流入（万元）
    hot_sectors: list[str]
    matched_sectors: list[str]
    signal_time: datetime
    strength: float = 0.0
    reasons: list[str] = field(default_factory=list)
