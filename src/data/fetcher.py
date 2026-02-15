"""數據獲取模組"""

import asyncio
from typing import Dict, List, Optional
import ccxt
from ..core.config import config
from ..core.logger import get_logger
from .simulator import MarketSimulator, MockExchangeClient

logger = get_logger(__name__)


class ExchangeClient:
    def __init__(self, exchange_id: str, exchange_config: Dict):
        self.exchange_id = exchange_id
        self.config = exchange_config
        self.exchange = None
        self._connect()
    
    def _connect(self):
        if not self.config.get('enabled', False):
            logger.info(f"{self.exchange_id} 已禁用")
            return
        
        exchange_class = getattr(ccxt, self.exchange_id)
        
        params = {
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        }
        
        if self.config.get('testnet', False):
            params['urls'] = {
                'api': {
                    'public': 'https://testnet.binance.vision/api',
                    'private': 'https://testnet.binance.vision/api',
                }
            }
        
        api_key = self.config.get('api_key')
        api_secret = self.config.get('api_secret')
        
        if api_key and api_secret:
            params['apiKey'] = api_key
            params['secret'] = api_secret
        
        try:
            self.exchange = exchange_class(params)
            logger.info(f"已連接交易所: {self.exchange_id}")
        except Exception as e:
            logger.error(f"連接交易所失敗 {self.exchange_id}: {e}")
    
    def is_connected(self) -> bool:
        return self.exchange is not None
    
    async def fetch_ticker(self, symbol: str) -> Optional[Dict]:
        if not self.is_connected():
            return None
        
        try:
            ticker = await asyncio.to_thread(self.exchange.fetch_ticker, symbol)
            return {
                'symbol': symbol,
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'last': ticker.get('last'),
                'quoteVolume': ticker.get('quoteVolume'),
                'timestamp': ticker.get('timestamp'),
            }
        except Exception as e:
            logger.warning(f"獲取價格失敗 {symbol}: {e}")
            return None
    
    async def fetch_order_book(self, symbol: str, limit: int = 10) -> Optional[Dict]:
        if not self.is_connected():
            return None
        
        try:
            orderbook = await asyncio.to_thread(self.exchange.fetch_order_book, symbol, limit)
            return {
                'symbol': symbol,
                'bids': orderbook.get('bids', []),
                'asks': orderbook.get('asks', []),
                'timestamp': orderbook.get('timestamp'),
            }
        except Exception as e:
            logger.warning(f"獲取深度失敗 {symbol}: {e}")
            return None
    
    async def fetch_balance(self) -> Optional[Dict]:
        if not self.is_connected():
            return None
        
        try:
            balance = await asyncio.to_thread(self.exchange.fetch_balance)
            return balance.get('total', {})
        except Exception as e:
            logger.warning(f"獲取餘額失敗: {e}")
            return None
    
    async def create_order(self, symbol: str, side: str, order_type: str, amount: float, price: Optional[float] = None) -> Optional[Dict]:
        if not self.is_connected():
            return None
        
        try:
            order = await asyncio.to_thread(self.exchange.create_order, symbol, order_type, side, amount, price)
            logger.info(f"訂單創建成功: {order['id']} {symbol} {side} {amount}")
            return order
        except Exception as e:
            logger.error(f"創建訂單失敗 {symbol}: {e}")
            return None


class DataFetcher:
    def __init__(self):
        self.exchanges: Dict[str, ExchangeClient] = {}
        
        self.simulation_mode = config.get('simulation.enabled', False)
        if self.simulation_mode:
            self.simulator = MarketSimulator(config._config)
            self._init_simulated_exchanges()
            logger.info("🎮 模擬模式啟動")
        else:
            self.simulator = None
            self._init_exchanges()
    
    def _init_exchanges(self):
        exchange_config = config.exchange
        
        for exchange_id, ex_config in exchange_config.items():
            if ex_config.get('enabled', False):
                self.exchanges[exchange_id] = ExchangeClient(exchange_id, ex_config)
        
        logger.info(f"已初始化交易所: {list(self.exchanges.keys())}")
    
    def _init_simulated_exchanges(self):
        exchange_config = config.exchange
        
        for exchange_id, ex_config in exchange_config.items():
            if ex_config.get('enabled', False):
                self.exchanges[exchange_id] = MockExchangeClient(exchange_id, self.simulator)
        
        logger.info(f"🎮 已初始化模擬交易所: {list(self.exchanges.keys())}")
    
    def get_exchange(self, exchange_id: str) -> Optional[ExchangeClient]:
        return self.exchanges.get(exchange_id)
    
    async def get_price(self, exchange_id: str, symbol: str) -> Optional[float]:
        client = self.get_exchange(exchange_id)
        if not client:
            return None
        
        ticker = await client.fetch_ticker(symbol)
        return ticker.get('last') if ticker else None
    
    async def get_spread(self, exchange_a: str, exchange_b: str, symbol: str) -> Optional[Dict]:
        price_a = await self.get_price(exchange_a, symbol)
        price_b = await self.get_price(exchange_b, symbol)
        
        if not price_a or not price_b:
            return None
        
        spread_pct = abs(price_a - price_b) / min(price_a, price_b) * 100
        
        return {
            'symbol': symbol,
            'price_a': price_a,
            'price_b': price_b,
            'spread': abs(price_a - price_b),
            'spread_pct': spread_pct,
            'direction': 'A_to_B' if price_a < price_b else 'B_to_A',
        }
    
    async def get_orderbook_spread(self, exchange_a: str, exchange_b: str, symbol: str) -> Optional[Dict]:
        client_a = self.get_exchange(exchange_a)
        client_b = self.get_exchange(exchange_b)
        
        if not client_a or not client_b:
            return None
        
        ob_a = await client_a.fetch_orderbook(symbol)
        ob_b = await client_b.fetch_orderbook(symbol)
        
        if not ob_a or not ob_b:
            return None
        
        best_bid_a = ob_a['bids'][0][0] if ob_a['bids'] else 0
        best_ask_a = ob_a['asks'][0][0] if ob_a['asks'] else 0
        best_bid_b = ob_b['bids'][0][0] if ob_b['bids'] else 0
        best_ask_b = ob_b['asks'][0][0] if ob_b['asks'] else 0
        
        profit_a_to_b = (best_bid_b - best_ask_a) / best_ask_a * 100
        profit_b_to_a = (best_bid_a - best_ask_b) / best_ask_b * 100
        
        return {
            'symbol': symbol,
            'exchange_a': {'bid': best_bid_a, 'ask': best_ask_a},
            'exchange_b': {'bid': best_bid_b, 'ask': best_ask_b},
            'profit_a_to_b': profit_a_to_b,
            'profit_b_to_a': profit_b_to_a,
        }