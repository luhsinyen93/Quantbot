"""突破策略"""

import asyncio
from typing import Dict, List, Optional

from .base import BaseStrategy, TradeSignal, SignalType
from ..data.fetcher import DataFetcher
from ..core.logger import get_logger

logger = get_logger(__name__)


class BreakoutStrategy(BaseStrategy):
    def __init__(self, data_fetcher: DataFetcher, strategy_config: Dict):
        super().__init__("Breakout", strategy_config)
        self.data_fetcher = data_fetcher
        self.period = strategy_config.get('period', 20)
        self.check_interval = strategy_config.get('check_interval', 60)
        self.symbols = strategy_config.get('symbols', [])
        
        logger.info(f"突破策略初始化: period={self.period}")
    
    async def get_data_requirements(self) -> List[str]:
        return ['ohlcv']
    
    async def analyze(self, data: Dict) -> Optional[TradeSignal]:
        if not self.enabled:
            return None
        
        for symbol in self.symbols:
            try:
                client = self.data_fetcher.get_exchange('mexc')
                if not client:
                    continue
                
                ohlcv = await client.fetch_ticker(symbol)
                
                if not ohlcv:
                    continue
                
                current_price = ohlcv.get('last', 0)
                high_24h = ohlcv.get('high', 0)
                low_24h = ohlcv.get('low', 0)
                
                if not current_price:
                    continue
                
                # 簡單突破邏輯
                if current_price > high_24h * 0.98:
                    quantity = 10 / current_price
                    
                    return TradeSignal(
                        symbol=symbol,
                        signal=SignalType.BUY,
                        price=current_price,
                        quantity=quantity,
                        reason=f"突破高點: {high_24h:.4f}",
                        confidence=0.6,
                        metadata={'strategy': 'breakout', 'direction': 'long'}
                    )
                
                elif current_price < low_24h * 1.02:
                    quantity = 10 / current_price
                    
                    return TradeSignal(
                        symbol=symbol,
                        signal=SignalType.SELL,
                        price=current_price,
                        quantity=quantity,
                        reason=f"跌破低點: {low_24h:.4f}",
                        confidence=0.6,
                        metadata={'strategy': 'breakout', 'direction': 'short'}
                    )
            
            except Exception as e:
                logger.warning(f"分析 {symbol} 時發生錯誤: {e}")
                continue
        
        return None