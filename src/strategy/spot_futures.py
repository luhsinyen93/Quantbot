"""現貨-合約套利策略"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from .base import BaseStrategy, TradeSignal, SignalType
from ..data.fetcher import DataFetcher
from ..core.config import config
from ..core.logger import get_logger

logger = get_logger(__name__)


class SpotFuturesArbitrageStrategy(BaseStrategy):
    def __init__(self, data_fetcher: DataFetcher, strategy_config: Dict):
        super().__init__("SpotFuturesArbitrage", strategy_config)
        self.data_fetcher = data_fetcher
        self.min_profit_ratio = strategy_config.get('min_profit_ratio', 0.002)
        self.check_interval = strategy_config.get('check_interval', 5)
        self.exchange_id = strategy_config.get('exchange', 'mexc')
        self.max_trade_amount = strategy_config.get('max_trade_amount', 10)
        self.max_slippage = strategy_config.get('max_slippage', 0.001)
        self.symbols = strategy_config.get('symbols', [])
        
        logger.info("📊 現貨-合約套利策略初始化")
    
    async def get_data_requirements(self) -> List[str]:
        return ['spot_ticker', 'futures_ticker']
    
    async def analyze(self, data: Dict) -> Optional[TradeSignal]:
        if not self.enabled:
            return None
        
        best_opportunity = None
        best_profit = 0
        
        for symbol in self.symbols:
            try:
                opportunity = await self._calculate_opportunity(symbol)
                
                if opportunity and opportunity.get('net_profit', 0) > self.min_profit_ratio * 100:
                    if opportunity['net_profit'] > best_profit:
                        best_profit = opportunity['net_profit']
                        best_opportunity = await self._create_signal(symbol, opportunity)
            
            except Exception as e:
                logger.warning(f"分析 {symbol} 時發生錯誤: {e}")
                continue
        
        if best_opportunity:
            logger.info(f"💰 發現現貨-合約套利機會: {best_opportunity.symbol}, 淨獲利: {best_profit:.3f}%")
        
        return best_opportunity
    
    async def _calculate_opportunity(self, symbol: str) -> Optional[Dict]:
        client = self.data_fetcher.get_exchange(self.exchange_id)
        if not client:
            return None
        
        try:
            spot_ticker = await client.fetch_ticker(symbol)
            if not spot_ticker:
                return None
            
            spot_price = spot_ticker.get('last', 0)
            spot_bid = spot_ticker.get('bid', 0)
            spot_ask = spot_ticker.get('ask', 0)
            
            if not spot_price:
                return None
            
            # 模擬合約價格（基差）
            import random
            basis_pct = random.uniform(-0.5, 1.0)
            futures_price = spot_price * (1 + basis_pct / 100)
            
            # 計算成本
            fee_pct = 0.3
            slippage_pct = self.max_slippage * 100
            
            gross_profit = basis_pct
            net_profit = gross_profit - fee_pct - slippage_pct
            
            return {
                'spot_price': spot_price,
                'futures_price': futures_price,
                'basis_pct': basis_pct,
                'net_profit': net_profit,
            }
        
        except Exception as e:
            logger.warning(f"計算套利失敗 {symbol}: {e}")
            return None
    
    async def _create_signal(self, symbol: str, opportunity: Dict) -> Optional[TradeSignal]:
        spot_price = opportunity['spot_price']
        quantity = self.max_trade_amount / spot_price
        expected_profit = self.max_trade_amount * (opportunity['net_profit'] / 100)
        return TradeSignal(
            symbol=symbol,
            signal=SignalType.BUY,
            price=spot_price,
            quantity=quantity,
            reason=f"現貨-合約套利: 基差={opportunity['basis_pct']:.3f}%, 淨獲利={opportunity['net_profit']:.3f}%",
            confidence=0.7,
            metadata={
                'strategy': 'spot_futures_arbitrage',
                'futures_price': opportunity['futures_price'],
                'basis_pct': opportunity['basis_pct'],
                'expected_profit': expected_profit,
            }
        )