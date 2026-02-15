"""智能交易器"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from ..data.fetcher import DataFetcher
from ..core.config import config
from ..core.logger import get_logger
from ..strategy.base import TradeSignal, SignalType
#from ..agent.trading_agent import AITradingAgent

logger = get_logger(__name__)


@dataclass
class TradeRecord:
    id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    entry_time: datetime
    exit_time: Optional[datetime] = None
    pnl: float = 0
    pnl_pct: float = 0
    status: str = 'open'
    metadata: Dict = field(default_factory=dict)


class SmartTrader:
    def __init__(self, data_fetcher: DataFetcher):
        self.data_fetcher = data_fetcher
        #self.ai_agent = AITradingAgent()
        
        self.trades: Dict[str, TradeRecord] = {}
        self.open_trades: Dict[str, TradeRecord] = {}
        self.closed_trades: List[TradeRecord] = []
        
        logger.info("SmartTrader 初始化完成")
    
    async def analyze_and_execute(self, signal: TradeSignal, market_data: Dict) -> Optional[TradeRecord]:
        logger.info(f"AI 分析中: {signal.symbol}...")
        
        # 簡化處理：直接執行
        trade = await self._execute_trade(signal)
        
        if trade:
            self.open_trades[trade.id] = trade
            self.trades[trade.id] = trade
        
        return trade
    
    async def _execute_trade(self, signal: TradeSignal) -> Optional[TradeRecord]:
        client = self.data_fetcher.get_exchange('mexc')
        if not client:
            logger.error("交易所未連接")
            return None
        
        try:
            side = 'buy' if signal.signal == SignalType.BUY else 'sell'
            
            order = await client.create_order(
                symbol=signal.symbol,
                side=side,
                order_type='market',
                amount=signal.quantity,
                price=None
            )
            
            if not order:
                return None
            
            trade = TradeRecord(
                id=order.get('id', f"trade_{datetime.now().timestamp()}"),
                symbol=signal.symbol,
                side=side,
                entry_price=order.get('price', signal.price),
                exit_price=None,
                quantity=signal.quantity,
                entry_time=datetime.now(),
                metadata={'reason': signal.reason}
            )
            
            logger.info(f"🎮 進場: {trade.symbol} @ {trade.entry_price}")
            
            return trade
        
        except Exception as e:
            logger.error(f"交易執行失敗: {e}")
            return None
    
    async def monitor_positions(self, market_data: Dict):
        for trade_id, trade in list(self.open_trades.items()):
            try:
                client = self.data_fetcher.get_exchange('mexc')
                if not client:
                    continue
                
                ticker = await client.fetch_ticker(trade.symbol)
                if not ticker:
                    continue
                
                current_price = ticker.get('last')
                
                # 計算未實現盈虧
                if trade.side == 'buy':
                    unrealized_pnl = (current_price - trade.entry_price) * trade.quantity
                else:
                    unrealized_pnl = (trade.entry_price - current_price) * trade.quantity
                
                pnl_pct = unrealized_pnl / (trade.entry_price * trade.quantity)
                
                # 檢查止損止盈
                risk_config = config.risk
                stop_loss = risk_config.get('stop_loss', 0.02)
                take_profit = risk_config.get('take_profit', 0.015)
                
                if pnl_pct <= -stop_loss or pnl_pct >= take_profit:
                    await self._close_trade(trade, current_price, "觸發止損/止盈")
            
            except Exception as e:
                logger.error(f"監控持倉失敗 {trade_id}: {e}")
    
    async def _close_trade(self, trade: TradeRecord, exit_price: float, reason: str):
        client = self.data_fetcher.get_exchange('mexc')
        if not client:
            return
        
        try:
            side = 'sell' if trade.side == 'buy' else 'buy'
            
            await client.create_order(
                symbol=trade.symbol,
                side=side,
                order_type='market',
                amount=trade.quantity,
                price=None
            )
            
            trade.exit_price = exit_price
            trade.exit_time = datetime.now()
            trade.status = 'closed'
            
            if trade.side == 'buy':
                trade.pnl = (exit_price - trade.entry_price) * trade.quantity
            else:
                trade.pnl = (trade.entry_price - exit_price) * trade.quantity
            
            trade.pnl_pct = trade.pnl / (trade.entry_price * trade.quantity)
            
            if trade.id in self.open_trades:
                del self.open_trades[trade.id]
            
            self.closed_trades.append(trade)
            
            logger.info(f"🎮 退場: {trade.symbol} @ {exit_price}, PnL: {trade.pnl:.2f}")
        
        except Exception as e:
            logger.error(f"平倉失敗: {e}")
    
    def get_trade_history(self, limit: int = 10) -> List[TradeRecord]:
        return self.closed_trades[-limit:]
    
    def get_open_positions(self) -> List[TradeRecord]:
        return list(self.open_trades.values())
    
    def get_performance_stats(self) -> Dict:
        if not self.closed_trades:
            return {'total_trades': 0, 'win_rate': 0, 'total_pnl': 0, 'avg_pnl': 0}
        
        total = len(self.closed_trades)
        wins = sum(1 for t in self.closed_trades if t.pnl > 0)
        total_pnl = sum(t.pnl for t in self.closed_trades)
        
        return {
            'total_trades': total,
            'win_rate': wins / total if total > 0 else 0,
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / total if total > 0 else 0,
            'win_trades': wins,
            'lose_trades': total - wins
        }