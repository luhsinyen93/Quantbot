"""交易執行模組"""

import asyncio
from typing import Dict, Optional
from datetime import datetime

from ..data.fetcher import DataFetcher
from ..core.config import config
from ..core.logger import get_logger
from ..strategy.base import TradeSignal, SignalType

logger = get_logger(__name__)


class Order:
    def __init__(self, id: str, symbol: str, side: str, type: str, amount: float, price: Optional[float], status: str = 'pending'):
        self.id = id
        self.symbol = symbol
        self.side = side
        self.type = type
        self.amount = amount
        self.price = price
        self.status = status


class Trade:
    def __init__(self, id: str, symbol: str, side: str, amount: float, price: float, pnl: float = 0):
        self.id = id
        self.symbol = symbol
        self.side = side
        self.amount = amount
        self.price = price
        self.pnl = pnl
        self.open_time = datetime.now()


class Trader:
    def __init__(self, data_fetcher: DataFetcher):
        self.data_fetcher = data_fetcher
        self.orders: Dict[str, Order] = {}
        self.trades: Dict[str, Trade] = {}
        
        logger.info("交易執行器初始化")
    
    async def execute_signal(self, signal: TradeSignal, exchange_id: str = 'mexc') -> Optional[Order]:
        client = self.data_fetcher.get_exchange(exchange_id)
        
        if not client:
            logger.error(f"交易所未連接: {exchange_id}")
            return None
        
        amount = signal.quantity
        
        if amount <= 0:
            logger.warning(f"訂單數量為0: {signal.symbol}")
            return None
        
        side = 'buy' if signal.signal == SignalType.BUY else 'sell'
        
        try:
            order = await client.create_order(
                symbol=signal.symbol,
                side=side,
                order_type='market',
                amount=amount,
                price=None
            )
            
            if order:
                logger.info(f"訂單成交: {order['id']} {side} {signal.symbol} {amount}")
                
                return Order(
                    id=order.get('id', ''),
                    symbol=signal.symbol,
                    side=side,
                    type='market',
                    amount=amount,
                    price=order.get('price'),
                    status='filled'
                )
        
        except Exception as e:
            logger.error(f"執行交易失敗: {signal.symbol} - {e}")
        
        return None
    
    def get_trade_history(self, limit: int = 10):
        trades = list(self.trades.values())
        trades.sort(key=lambda x: x.open_time, reverse=True)
        return trades[:limit]