"""策略基類"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class TradeSignal:
    symbol: str
    signal: SignalType
    price: float
    quantity: float
    reason: str
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)


@dataclass
class Position:
    symbol: str
    side: str
    entry_price: float
    quantity: float
    entry_time: datetime = field(default_factory=datetime.now)
    unrealized_pnl: float = 0.0
    
    @property
    def value(self) -> float:
        return self.entry_price * self.quantity


class BaseStrategy(ABC):
    def __init__(self, name: str, config: Dict):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
        self.positions: Dict[str, Position] = {}
    
    @abstractmethod
    async def analyze(self, data: Dict) -> Optional[TradeSignal]:
        pass
    
    @abstractmethod
    async def get_data_requirements(self) -> List[str]:
        pass
    
    def can_trade(self, symbol: str) -> bool:
        if not self.enabled:
            return False
        return True
    
    def update_position(self, position: Position):
        self.positions[position.symbol] = position
    
    def close_position(self, symbol: str):
        if symbol in self.positions:
            del self.positions[symbol]
    
    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)
    
    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions