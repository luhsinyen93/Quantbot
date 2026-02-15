"""風險管理模組"""

from typing import Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque

from ..core.config import config
from ..core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RiskState:
    daily_pnl: float = 0
    consecutive_losses: int = 0
    api_errors: int = 0
    total_trades: int = 0
    is_paused: bool = False
    pause_until: Optional[datetime] = None


class RiskManager:
    def __init__(self):
        self.config = config.risk
        self.state = RiskState()
        
        self.stop_loss = self.config.get('stop_loss', 0.02)
        self.take_profit = self.config.get('take_profit', 0.015)
        self.max_daily_loss = self.config.get('max_daily_loss', 0.10)
        self.max_consecutive_losses = self.config.get('max_consecutive_losses', 3)
        self.pause_minutes = self.config.get('pause_minutes', 30)
        
        self.initial_capital = config.trading.get('initial_capital', 100)
        
        logger.info(f"風險管理器初始化: 止損{self.stop_loss*100}%, 止盈{self.take_profit*100}%")
    
    def can_trade(self) -> tuple:
        if self.state.is_paused:
            if self.state.pause_until and datetime.now() < self.state.pause_until:
                remaining = (self.state.pause_until - datetime.now()).seconds // 60
                return False, f"策略暫停中，{remaining}分鐘後恢復"
            else:
                self.state.is_paused = False
        
        if self.state.daily_pnl <= -self.initial_capital * self.max_daily_loss:
            self._pause_trading("日內虧損達限額")
            return False, f"日內虧損達到{self.max_daily_loss*100}%"
        
        return True, "OK"
    
    def record_trade_result(self, pnl: float, is_win: bool):
        self.state.total_trades += 1
        self.state.daily_pnl += pnl
        
        if is_win:
            self.state.consecutive_losses = 0
            logger.info(f"交易獲利: +{pnl:.2f}")
        else:
            self.state.consecutive_losses += 1
            logger.warning(f"交易虧損: {pnl:.2f}, 連續虧損: {self.state.consecutive_losses}")
            
            if self.state.consecutive_losses >= self.max_consecutive_losses:
                self._pause_trading(f"連續虧損{self.state.consecutive_losses}次")
    
    def _pause_trading(self, reason: str):
        self.state.is_paused = True
        self.state.pause_until = datetime.now() + timedelta(minutes=self.pause_minutes)
        logger.warning(f"交易暫停: {reason}")
    
    def get_status(self) -> Dict:
        return {
            'daily_pnl': self.state.daily_pnl,
            'total_trades': self.state.total_trades,
            'consecutive_losses': self.state.consecutive_losses,
            'is_paused': self.state.is_paused,
            'can_trade': self.can_trade()[0],
        }
    
    def reset_daily(self):
        self.state.daily_pnl = 0
        logger.info("每日風險狀態已重置")


class PortfolioManager:
    def __init__(self, risk_manager: RiskManager):
        self.risk_manager = risk_manager
        self.positions: Dict[str, Dict] = {}
        self.max_positions = config.trading.get('max_positions', 10)
    
    def open_position(self, symbol: str, side: str, entry_price: float, quantity: float) -> bool:
        if len(self.positions) >= self.max_positions:
            logger.warning(f"已達最大持倉數: {self.max_positions}")
            return False
        
        if symbol in self.positions:
            return False
        
        self.positions[symbol] = {
            'side': side, 'entry_price': entry_price,
            'quantity': quantity, 'entry_time': datetime.now()
        }
        
        logger.info(f"開倉: {symbol} {side} @ {entry_price}")
        return True
    
    def close_position(self, symbol: str) -> Optional[Dict]:
        if symbol in self.positions:
            position = self.positions.pop(symbol)
            logger.info(f"平倉: {symbol}")
            return position
        return None
    def get_positions(self) -> Dict:
        return self.positions.copy()