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


@dataclass
class AuctionSignal:
    """集合竞价信号"""

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
