"""資金費套利策略

原理：
1. 永續合約每8小時結算一次資金費
2. 當資金費為正時，做空合約的人要付錢
3. 策略：現貨買入 + 合約做空，持有到結算，賺取資金費
4. 同時如果基差有利，還能賺到價差收益
"""

import asyncio
import random
from typing import Dict, List, Optional
from datetime import datetime

from .base import BaseStrategy, TradeSignal, SignalType
from ..data.fetcher import DataFetcher
from ..core.config import config
from ..core.logger import get_logger

logger = get_logger(__name__)


class FundingArbitrageStrategy(BaseStrategy):
    """資金費套利策略"""
    
    def __init__(self, data_fetcher: DataFetcher, strategy_config: Dict):
        super().__init__("FundingArbitrage", strategy_config)
        self.data_fetcher = data_fetcher
        self.min_funding_rate = strategy_config.get('min_funding_rate', 0.0001)
        self.check_interval = strategy_config.get('check_interval', 300)
        self.exchange_id = strategy_config.get('exchange', 'mexc')
        self.max_trade_amount = strategy_config.get('max_trade_amount', 10)
        
        # 永續合約對應的現貨
        self.perp_to_spot = {
            "BTC-USDT": "BTC/USDT",
            "ETH-USDT": "ETH/USDT",
            "SOL-USDT": "SOL/USDT",
        }
        
        logger.info("💰 資金費套利策略初始化")
    
    async def get_data_requirements(self) -> List[str]:
        return ['perp_ticker', 'spot_ticker', 'funding_rate']
    
    async def analyze(self, data: Dict) -> Optional[TradeSignal]:
        if not self.enabled:
            return None
        
        best_opportunity = None
        best_profit = 0
        
        for perp_symbol, spot_symbol in self.perp_to_spot.items():
            try:
                opportunity = await self._check_funding_opportunity(perp_symbol, spot_symbol)
                
                if opportunity and opportunity['expected_profit'] > best_profit:
                    best_profit = opportunity['expected_profit']
                    best_opportunity = await self._create_signal(spot_symbol, opportunity)
            
            except Exception as e:
                continue
        
        if best_opportunity:
            logger.info(f"💰 發現資金費套利機會: {best_opportunity.symbol}")
        
        return best_opportunity
    
    async def _check_funding_opportunity(self, perp_symbol: str, spot_symbol: str) -> Optional[Dict]:
        client = self.data_fetcher.get_exchange(self.exchange_id)
        if not client:
            return None
        
        try:
            perp_ticker = await client.fetch_ticker(perp_symbol)
            spot_ticker = await client.fetch_ticker(spot_symbol)
            
            if not perp_ticker or not spot_ticker:
                return None
            
            perp_price = perp_ticker.get('last', 0)
            spot_price = spot_ticker.get('last', 0)
            
            if not perp_price or not spot_price:
                return None
            
            # 模擬資金費率
            funding_rate = random.uniform(-0.0005, 0.001)
            
            # 計算基差
            basis = (perp_price - spot_price) / spot_price * 100
            
            # 預期收益
            funding_profit = funding_rate * 3
            basis_profit = -basis * 0.5
            total_profit = funding_profit + basis_profit
            fee = 0.3
            net_profit = total_profit - fee
            
            return {
                'perp_symbol': perp_symbol,
                'spot_symbol': spot_symbol,
                'perp_price': perp_price,
                'spot_price': spot_price,
                'funding_rate': funding_rate,
                'basis': basis,
                'expected_profit': net_profit,
            }
        
        except Exception as e:
            return None
    
    async def _create_signal(self, symbol: str, opportunity: Dict) -> Optional[TradeSignal]:
        quantity = self.max_trade_amount / opportunity['spot_price']
        return TradeSignal(
            symbol=symbol,
            signal=SignalType.BUY,
            price=opportunity['spot_price'],
            quantity=quantity,
            reason=f"資金費套利: 資金費率={opportunity['funding_rate']*100:.4f}%, 預期收益={opportunity['expected_profit']:.4f}%",
            confidence=0.8,
            metadata={
                'strategy': 'funding_arbitrage',
                'perp_symbol': opportunity['perp_symbol'],
                'perp_price': opportunity['perp_price'],
                'funding_rate': opportunity['funding_rate'],
                'basis': opportunity['basis'],
            }
        )


class PerpetualBasisStrategy(BaseStrategy):
    """永續合約基差套利"""
    
    def __init__(self, data_fetcher: DataFetcher, strategy_config: Dict):
        super().__init__("PerpetualBasis", strategy_config)
        self.data_fetcher = data_fetcher
        self.min_profit_ratio = strategy_config.get('min_profit_ratio', 0.001)
        self.check_interval = strategy_config.get('check_interval', 60)
        self.exchange_id = strategy_config.get('exchange', 'mexc')
        self.max_trade_amount = strategy_config.get('max_trade_amount', 10)
        
        self.perp_symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
        
        logger.info("📊 永續基差套利初始化")
    
    async def get_data_requirements(self) -> List[str]:
        return ['perp_ticker', 'spot_ticker']
    
    async def analyze(self, data: Dict) -> Optional[TradeSignal]:
        if not self.enabled:
            return None
        
        for perp in self.perp_symbols:
            try:
                spot = perp.replace("-", "/")
                opp = await self._check_basis(perp, spot)
                
                if opp and opp['net_profit'] > self.min_profit_ratio * 100:
                    return await self._create_signal(spot, opp)
            except:
                continue
        
        return None
    
    async def _check_basis(self, perp_symbol: str, spot_symbol: str) -> Optional[Dict]:
        client = self.data_fetcher.get_exchange(self.exchange_id)
        if not client:
            return None
        
        try:
            perp_ticker = await client.fetch_ticker(perp_symbol)
            spot_ticker = await client.fetch_ticker(spot_symbol)
            
            if not perp_ticker or not spot_ticker:
                return None
            
            perp_price = perp_ticker.get('last', 0)
            spot_price = spot_ticker.get('last', 0)
            
            basis = (perp_price - spot_price) / spot_price * 100
            expected_convergence = abs(basis) * 0.3
            net_profit = expected_convergence - 0.3
            
            return {
                'perp_symbol': perp_symbol,
                'spot_symbol': spot_symbol,
                'perp_price': perp_price,
                'spot_price': spot_price,
                'basis': basis,
                'net_profit': net_profit,
            }
        except:
            return None
    
    async def _create_signal(self, symbol: str, opportunity: Dict) -> Optional[TradeSignal]:
        quantity = self.max_trade_amount / opportunity['spot_price']
        
        return TradeSignal(
            symbol=symbol,
            signal=SignalType.BUY,
            price=opportunity['spot_price'],
            quantity=quantity,
            reason=f"基差套利: 基差={opportunity['basis']:.3f}%",
            confidence=0.7,
            metadata={
                'strategy': 'perpetual_basis',
                'perp_symbol': opportunity['perp_symbol'],
            }
        )