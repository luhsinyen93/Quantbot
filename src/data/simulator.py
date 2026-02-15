"""模擬市場數據產生器"""

import random
import time
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass

from ..core.logger import get_logger

logger = get_logger(__name__)


BASE_PRICES = {
    "BTC/USDT": 50000,
    "ETH/USDT": 3000,
    "SOL/USDT": 100,
    "XRP/USDT": 0.5,
    "ADA/USDT": 0.35,
}


@dataclass
class MockTicker:
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: int


@dataclass
class MockOrderBook:
    bids: list
    asks: list
    timestamp: int


class MarketSimulator:
    def __init__(self, config: Dict):
        self.config = config
        sim = config.get('simulation', {})
        self.enabled = sim.get('enabled', False)
        self.price_change_range = sim.get('price_change_range', 0.02)
        self.arbitrage_opportunity_rate = sim.get('arbitrage_opportunity_rate', 0.3)
        
        self.current_prices = BASE_PRICES.copy()
        
        logger.info(f"🎮 市場模擬器初始化: enabled={self.enabled}")
    
    def _generate_price(self, symbol: str) -> float:
        base = BASE_PRICES.get(symbol, 100)
        change = random.uniform(-self.price_change_range, self.price_change_range)
        price = base * (1 + change)
        return round(price, 4 if price >= 1 else 8)
    
    def _generate_orderbook(self, price: float):
        spread = price * random.uniform(0.0005, 0.002)
        bid = price - spread / 2
        ask = price + spread / 2
        
        bids = []
        asks = []
        
        for i in range(10):
            bids.append([bid * (1 - i * 0.001), random.uniform(100, 10000)])
            asks.append([ask * (1 + i * 0.001), random.uniform(100, 10000)])
        
        return bids, asks
    
    def generate_ticker(self, symbol: str) -> MockTicker:
        price = self._generate_price(symbol)
        bids, asks = self._generate_orderbook(price)
        
        return MockTicker(
            symbol=symbol,
            bid=bids[0][0],
            ask=asks[0][0],
            last=price,
            volume=random.uniform(1000000, 10000000),
            timestamp=int(time.time() * 1000)
        )
    
    def generate_orderbook(self, symbol: str) -> MockOrderBook:
        price = self._generate_price(symbol)
        bids, asks = self._generate_orderbook(price)
        
        return MockOrderBook(
            bids=bids,
            asks=asks,
            timestamp=int(time.time() * 1000)
        )
    
    def generate_arbitrage_opportunity(self, symbol: str) -> Optional[Dict]:
        if random.random() > self.arbitrage_opportunity_rate:
            return None
        
        price_a = self._generate_price(symbol)
        
        if random.random() > 0.5:
            price_b = price_a * (1 + random.uniform(0.003, 0.015))
        else:
            price_b = price_a * (1 - random.uniform(0.003, 0.015))
            price_a = price_b
        
        raw_spread = abs(price_a - price_b) / min(price_a, price_b) * 100
        
        return {
            'symbol': symbol,
            'mexc': {'bid': price_b, 'ask': price_a},
            'bitget': {'bid': price_a, 'ask': price_b},
            'raw_spread': raw_spread,
        }
    
    def get_mock_balance(self) -> Dict:
        return {
            'USDT': 100.0,
            'BTC': 0.001,
            'ETH': 0.01,
        }


class MockExchangeClient:
    def __init__(self, exchange_id: str, simulator: MarketSimulator):
        self.exchange_id = exchange_id
        self.simulator = simulator
        self.connected = True
    
    def is_connected(self) -> bool:
        return self.connected
    
    async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        ticker = self.simulator.generate_ticker(symbol)
        return {
            'symbol': symbol,
            'bid': ticker.bid,
            'ask': ticker.ask,
            'last': ticker.last,
            'quoteVolume': ticker.volume,
            'timestamp': ticker.timestamp
        }
    
    async def fetch_orderbook(self, symbol: str, limit: int = 10) -> Optional[Dict]:
        ob = self.simulator.generate_orderbook(symbol)
        return {
            'symbol': symbol,
            'bids': ob.bids,
            'asks': ob.asks,
            'timestamp': ob.timestamp
        }
    
    async def fetch_balance(self) -> Dict:
        return self.simulator.get_mock_balance()
    
    async def create_order(self, symbol: str, side: str, order_type: str, amount: float, price: Optional[float] = None) -> Optional[Dict]:
        actual_price = price if price else self.simulator._generate_price(symbol)
        
        logger.info(f"🎮 [模擬] {side} {amount} {symbol} @ {actual_price}")
        
        return {
            'id': f"mock_{int(time.time() * 1000)}",
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'amount': amount,
            'price': actual_price,
            'status': 'filled',
            'filled': amount,
            'remaining': 0,
        }