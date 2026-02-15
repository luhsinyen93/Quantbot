"""QuantBot 主程式 - 整合 AI Agent"""

import asyncio
import signal
from typing import Dict, List, Optional
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import config
from .logger import get_logger

# 根據是否存在來導入
try:
    from ..data.fetcher import DataFetcher
except ImportError:
    DataFetcher = None

try:
    from ..strategy import ArbitrageStrategy, SpotFuturesArbitrageStrategy, BreakoutStrategy
except ImportError:
    ArbitrageStrategy = None
    SpotFuturesArbitrageStrategy = None
    BreakoutStrategy = None

try:
    from ..trading import SmartTrader
except ImportError:
    SmartTrader = None

try:
    from ..risk import RiskManager, PortfolioManager
except ImportError:
    RiskManager = None
    PortfolioManager = None

try:
    from ..agent import AITradingAgent
except ImportError:
    AITradingAgent = None

try:
    from ..notification import notifier
except ImportError:
    notifier = None

logger = get_logger(__name__)


class QuantBot:
    def __init__(self):
        # 初始化組件
        self.data_fetcher = DataFetcher() if DataFetcher else None
        self.smart_trader = SmartTrader(self.data_fetcher) if SmartTrader and self.data_fetcher else None
        self.risk_manager = RiskManager() if RiskManager else None
        self.portfolio = PortfolioManager(self.risk_manager) if PortfolioManager and self.risk_manager else None
        
        # AI Agent（暫時移除）
        self.ai_agent = None  # AITradingAgent() if AITradingAgent else None
        
        # 策略
        self.strategies: List = []
        self._init_strategies()
        
        # 排程器
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        
        # 設定信號處理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # 啟動 Web 服務器
        self._start_web_server()
        
        logger.info("QuantBot (AI版) 初始化完成")
    
    def _start_web_server(self):
        """啟動 Web 控制面板"""
        try:
            from ..web import init_app, run_server, add_log
            
            init_app(self)
            
            web_port = config.get('web.port', 5000)
            import threading
            web_thread = threading.Thread(target=run_server, kwargs={'port': web_port}, daemon=True)
            web_thread.start()
            
            logger.info(f"🌐 Web 控制面板已啟動: http://localhost:{web_port}")
            add_log(f"Web 控制面板已啟動", "success")
        except Exception as e:
            logger.warning(f"Web 服務器跳過: {e}")
    
    def _init_strategies(self):
        if not config.strategy:
            return
        
        strategy_config = config.strategy
        
        if ArbitrageStrategy and strategy_config.get('cross_exchange_arbitrage', {}).get('enabled', False):
            arbitrage = ArbitrageStrategy(self.data_fetcher, strategy_config['cross_exchange_arbitrage'])
            self.strategies.append(arbitrage)
            logger.info("✅ 交易所間套利策略已啟用")
        
        if SpotFuturesArbitrageStrategy and strategy_config.get('spot_futures_arbitrage', {}).get('enabled', False):
            spot_futures = SpotFuturesArbitrageStrategy(self.data_fetcher, strategy_config['spot_futures_arbitrage'])
            self.strategies.append(spot_futures)
            logger.info("✅ 現貨-合約套利策略已啟用")
        
        logger.info(f"已加載 {len(self.strategies)} 個策略")
    
    def _signal_handler(self, signum, frame):
        logger.info("收到停止信號，正在關閉...")
        self.stop()
    
    async def start(self):
        logger.info("=" * 50)
        logger.info("QuantBot AI 版啟動")
        
        if self.data_fetcher and hasattr(self.data_fetcher, 'simulation_mode') and self.data_fetcher.simulation_mode:
            logger.info("🎮 模式: 模擬交易 (測試中)")
        else:
            logger.info("💰 模式: 真實交易")
        
        logger.info("=" * 50)
        if not self._check_exchanges():
            logger.error("交易所連接失敗，無法啟動")
            return
        
        if self.risk_manager:
            can_trade, reason = self.risk_manager.can_trade()
            if not can_trade:
                logger.warning(f"風險檢查: {reason}")
        
        self._setup_jobs()
        self.scheduler.start()
        
        self.is_running = True
        
        if notifier:
            try:
                await notifier.send("🤖 *QuantBot 已啟動*")
            except:
                pass
        
        try:
            while self.is_running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"運行錯誤: {e}")
            self.stop()
    
    def _check_exchanges(self) -> bool:
        if not self.data_fetcher:
            return True
        for exchange_id, client in self.data_fetcher.exchanges.items():
            if client.is_connected():
                logger.info(f"✓ {exchange_id} 已連接")
            else:
                logger.warning(f"✗ {exchange_id} 未連接")
                return False
        return True
    
    def _setup_jobs(self):
        if self.risk_manager:
            self.scheduler.add_job(self.risk_manager.reset_daily, 'cron', hour=0, minute=0, id='daily_reset')
        
        for strategy in self.strategies:
            interval = strategy.check_interval if hasattr(strategy, 'check_interval') else 60
            self.scheduler.add_job(self.run_strategy, 'interval', seconds=interval, id=f'strategy_{strategy.name}', args=[strategy])
        
        logger.info(f"已設定 {len(self.scheduler.get_jobs())} 個排程任務")
    
    async def run_strategy(self, strategy):
        if self.risk_manager:
            can_trade, reason = self.risk_manager.can_trade()
            if not can_trade:
                return
        
        try:
            signal = await strategy.analyze({})
            
            if signal and self.smart_trader:
                market_data = await self._prepare_market_data(signal)
                await self.smart_trader.analyze_and_execute(signal, market_data)
        
        except Exception as e:
            logger.error(f"策略執行錯誤 {strategy.name}: {e}")
    
    async def _prepare_market_data(self, signal) -> Dict:
        market_data = {'symbol': signal.symbol, 'price': signal.price, 'metadata': signal.metadata}
        
        if self.data_fetcher:
            try:
                client = self.data_fetcher.get_exchange('mexc')
                if client:
                    ticker = await client.fetch_ticker(signal.symbol)
                    if ticker:
                        market_data.update({'bid': ticker.get('bid'), 'ask': ticker.get('ask'), 'volume': ticker.get('quoteVolume')})
            except Exception as e:
                logger.warning(f"獲取市場數據失敗: {e}")
        
        return market_data
    
    def stop(self):
        logger.info("QuantBot 停止中...")
        self.is_running = False
        
        if self.scheduler.running:
            self.scheduler.shutdown()
        
        status = self.get_status()
        logger.info("QuantBot 已停止")
    
    def get_status(self) -> Dict:
        stats = {'total_trades': 0, 'win_rate': 0, 'total_pnl': 0, 'positions': 0}
        
        if self.smart_trader:
            stats = self.smart_trader.get_performance_stats()
        
        risk_status = {'daily_pnl': 0, 'is_paused': False}
        
        if self.risk_manager:
            risk_status = self.risk_manager.get_status()
        
        return {
            'running': self.is_running,
            'strategies': len(self.strategies),
            'total_trades': stats.get('total_trades', 0),
            'win_rate': stats.get('win_rate', 0),
            'total_pnl': stats.get('total_pnl', 0),
            'daily_pnl': risk_status.get('daily_pnl', 0),
            'is_paused': risk_status.get('is_paused', False),
            'positions': len(self.smart_trader.get_open_positions()) if self.smart_trader else 0,
            }