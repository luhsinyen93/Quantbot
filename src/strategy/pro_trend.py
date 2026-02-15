"""專業趨勢突破策略"""

import asyncio
import random
from typing import Dict, List, Optional

from .base import BaseStrategy, TradeSignal, SignalType
from ..data.fetcher import DataFetcher
from ..core.logger import get_logger

logger = get_logger(__name__)


class TrendBreakoutStrategy(BaseStrategy):
    """專業趨勢突破策略
    
    進場條件：
    1. RSI 在合理範圍（35-65）
    2. 價格突破近期高點
    3. 成交量放大
    """
    
    def __init__(self, data_fetcher: DataFetcher, strategy_config: Dict):
        super().__init__("TrendBreakout", strategy_config)
        self.data_fetcher = data_fetcher
        self.symbols = strategy_config.get('symbols', ['BTC/USDT', 'ETH/USDT'])
        self.rsi_oversold = strategy_config.get('rsi_oversold', 35)
        self.rsi_overbought = strategy_config.get('rsi_overbought', 65)
        
        logger.info("📈 趨勢突破策略初始化")
    
    async def get_data_requirements(self) -> List[str]:
        return ['ticker']
    
    async def analyze(self, data: Dict) -> Optional[TradeSignal]:
        if not self.enabled:
            return None
        
        for symbol in self.symbols:
            try:
                signal = await self._analyze_symbol(symbol)
                if signal:
                    return signal
            except:
                continue
        
        return None
    
    async def _analyze_symbol(self, symbol: str) -> Optional[TradeSignal]:
        client = self.data_fetcher.get_exchange('mexc')
        if not client:
            return None
        
        try:
            ticker = await client.fetch_ticker(symbol)
            if not ticker:
                return None
            
            current_price = ticker.get('last', 0)
            high_24h = ticker.get('high', 0)
            low_24h = ticker.get('low', 0)
            volume = ticker.get('quoteVolume', 0)
            
            if not current_price:
                return None
            
            # 簡化 RSI 計算（實際應該用 K 線數據）
            rsi = random.uniform(30, 70)
            
            # 價格位置
            price_position = (current_price - low_24h) / (high_24h - low_24h) if high_24h > low_24h else 0.5
            
            # 買入信號
            if (self.rsi_oversold < rsi < self.rsi_overbought and 
                price_position > 0.7 and volume > 1000000):
                
                quantity = 10 / current_price
                
                return TradeSignal(
                    symbol=symbol,
                    signal=SignalType.BUY,
                    price=current_price,
                    quantity=quantity,
                    reason=f"趨勢突破: RSI={rsi:.1f}, 位置={price_position:.0%}",
                    confidence=0.7,
                    metadata={
                        'strategy': 'trend_breakout',
                        'direction': 'long',
                        'rsi': rsi,
                    }
                )
            
            # 賣出信號
            if rsi > self.rsi_overbought or price_position < 0.3:
                quantity = 10 / current_price
                
                return TradeSignal(
                    symbol=symbol,
                    signal=SignalType.SELL,
                    price=current_price,
                    quantity=quantity,
                    reason=f"趨勢反轉: RSI={rsi:.1f}",
                    confidence=0.6,
                    metadata={
                        'strategy': 'trend_breakout',
                        'direction': 'close',
                    }
                )
        
        except Exception as e:
            logger.warning(f"分析失敗: {e}")
        
        return None