"""套利策略"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from .base import BaseStrategy, TradeSignal, SignalType
from ..data.fetcher import DataFetcher
from ..core.config import config
from ..core.logger import get_logger

logger = get_logger(__name__)


class ArbitrageStrategy(BaseStrategy):
    def __init__(self, data_fetcher: DataFetcher, strategy_config: Dict):
        super().__init__("Arbitrage", strategy_config)
        self.data_fetcher = data_fetcher
        self.min_profit_ratio = strategy_config.get('min_profit_ratio', 0.003)
        self.check_interval = strategy_config.get('check_interval', 3)
        self.pairs = strategy_config.get('pairs', [])
        
        self.exchange_a = strategy_config.get('exchange_a', 'mexc')
        self.exchange_b = strategy_config.get('exchange_b', 'bitget')
        self.max_arbitrage_amount = strategy_config.get('max_arbitrage_amount', 10)
        
        exchange_cfg = config.exchange
        self.fee_buy_a = exchange_cfg.get(self.exchange_a, {}).get('taker_fee', 0.002)
        self.fee_sell_b = exchange_cfg.get(self.exchange_b, {}).get('taker_fee', 0.001)
        
        logger.info(f"🤖 套利策略初始化: {self.exchange_a} ↔ {self.exchange_b}")
    
    async def get_data_requirements(self) -> List[str]:
        return ['ticker', 'orderbook']
    
    async def analyze(self, data: Dict) -> Optional[TradeSignal]:
        if not self.enabled:
            return None
        
        best_opportunity = None
        best_profit = 0
        
        for pair in self.pairs:
            symbol = pair[0]
            
            try:
                spread_data = await self.data_fetcher.get_orderbook_spread(
                    self.exchange_a, self.exchange_b, symbol
                )
                
                if not spread_data:
                    continue
                
                profit_a_to_b = spread_data.get('profit_a_to_b', 0)
                profit_b_to_a = spread_data.get('profit_b_to_a', 0)
                
                if profit_a_to_b > best_profit and profit_a_to_b > self.min_profit_ratio * 100:
                    best_profit = profit_a_to_b
                    best_opportunity = await self._create_signal(symbol, spread_data, 'A_to_B', profit_a_to_b)
                
                if profit_b_to_a > best_profit and profit_b_to_a > self.min_profit_ratio * 100:
                    best_profit = profit_b_to_a
                    best_opportunity = await self._create_signal(symbol, spread_data, 'B_to_A', profit_b_to_a)
            
            except Exception as e:
                logger.warning(f"分析 {symbol} 時發生錯誤: {e}")
                continue
        
        if best_opportunity:
            logger.info(f"💰 發現套利機會: {best_opportunity.symbol}, 淨獲利: {best_profit:.3f}%")
        
        return best_opportunity
    
    async def _create_signal(self, symbol: str, spread_data: Dict, direction: str, profit_pct: float) -> Optional[TradeSignal]:
        if direction == 'A_to_B':
            buy_exchange = self.exchange_a
            sell_exchange = self.exchange_b
            buy_price = spread_data['exchange_a']['ask']
            sell_price = spread_data['exchange_b']['bid']
        else:
            buy_exchange = self.exchange_b
            sell_exchange = self.exchange_a
            buy_price = spread_data['exchange_b']['ask']
            sell_price = spread_data['exchange_a']['bid']
        
        quantity = self.max_arbitrage_amount / buy_price
        expected_profit = self.max_arbitrage_amount * (profit_pct / 100)
        return TradeSignal(
            symbol=symbol,
            signal=SignalType.BUY,
            price=buy_price,
            quantity=quantity,
            reason=f"套利: {buy_exchange} 買入 → {sell_exchange} 賣出, 預期獲利 {profit_pct:.3f}%",
            confidence=0.8,
            metadata={
                'strategy': 'arbitrage',
                'direction': direction,
                'profit_pct': profit_pct,
                'exchange_buy': buy_exchange,
                'exchange_sell': sell_exchange,
                'expected_profit': expected_profit,
            }
        )