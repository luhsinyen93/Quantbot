"""QuantBot 主程式"""

import asyncio
import signal
from typing import Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import config
from .logger import get_logger

logger = get_logger(__name__)


class QuantBot:
    def __init__(self):
        # 初始化組件
        try:
            from ..data.fetcher import DataFetcher
            self.data_fetcher = DataFetcher()
        except:
            self.data_fetcher = None
        
        try:
            from ..trading import SmartTrader
            self.smart_trader = SmartTrader(self.data_fetcher) if self.data_fetcher else None
        except:
            self.smart_trader = None
        
        try:
            from ..risk import RiskManager
            self.risk_manager = RiskManager()
        except:
            self.risk_manager = None
        
        # 策略
        self.strategies: List = []
        self._init_strategies()
        
        # 排程器
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        
        # 信號處理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Web
        self._start_web_server()
        
        logger.info("QuantBot 初始化完成")
    
    def _init_strategies(self):
        if not config.strategy:
            return
        
        strategy_config = config.strategy
        
        # 資金費套利
        if strategy_config.get('funding_arbitrage', {}).get('enabled', False):
            try:
                from ..strategy import FundingArbitrageStrategy
                s = FundingArbitrageStrategy(self.data_fetcher, strategy_config['funding_arbitrage'])
                self.strategies.append(s)
                logger.info("💰 資金費套利策略已啟用")
            except Exception as e:
                logger.warning(f"資金費套利載入失敗: {e}")
        
        # 基差套利
        if strategy_config.get('perpetual_arbitrage', {}).get('enabled', False):
            try:
                from ..strategy import PerpetualBasisStrategy
                s = PerpetualBasisStrategy(self.data_fetcher, strategy_config['perpetual_arbitrage'])
                self.strategies.append(s)
                logger.info("📊 基差套利策略已啟用")
            except Exception as e:
                logger.warning(f"基差套利載入失敗: {e}")
        
        # 趨勢突破
        if strategy_config.get('trend_breakout', {}).get('enabled', False):
            try:
                from ..strategy import TrendBreakoutStrategy
                s = TrendBreakoutStrategy(self.data_fetcher, strategy_config['trend_breakout'])
                self.strategies.append(s)
                logger.info("📈 趨勢突破策略已啟用")
            except Exception as e:
                logger.warning(f"趨勢突破載入失敗: {e}")
        
        logger.info(f"已加載 {len(self.strategies)} 個策略")
    
    def _start_web_server(self):
        try:
            from ..web import init_app, run_server, add_log
            init_app(self)
            import threading
            web_port = config.get('web.port', 5000)
            web_thread = threading.Thread(target=run_server, kwargs={'port': web_port}, daemon=True)
            web_thread.start()
            logger.info(f"🌐 Web 控制面板已啟動")
        except Exception as e:
            logger.warning(f"Web 服務器跳過: {e}")
    
    def _signal_handler(self, signum, frame):
        logger.info("收到停止信號，正在關閉...")
        self.stop()
    
    async def start(self):
        logger.info("=" * 50)
        logger.info("QuantBot AI 版啟動")
        
        if self.data_fetcher and hasattr(self.data_fetcher, 'simulation_mode'):
            logger.info("🎮 模式: 模擬交易")
        else:
            logger.info("💰 模式: 真實交易")
        
        logger.info("=" * 50)
        
        self._setup_jobs()
        self.scheduler.start()
        
        self.is_running = True
        
        try:
            while self.is_running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"運行錯誤: {e}")
            self.stop()
    
    def _setup_jobs(self):
        for strategy in self.strategies:
            interval = strategy.check_interval if hasattr(strategy, 'check_interval') else 60
            self.scheduler.add_job(
                self.run_strategy, 'interval', seconds=interval,
                id=f'strategy_{strategy.name}', args=[strategy]
            )
        logger.info(f"已設定 {len(self.scheduler.get_jobs())} 個排程任務")
    
    async def run_strategy(self, strategy):
        try:
            signal = await strategy.analyze({})
            if signal and self.smart_trader:
                await self.smart_trader.analyze_and_execute(signal, {})
        except Exception as e:
            logger.error(f"策略執行錯誤: {e}")
    
    def stop(self):
        logger.info("QuantBot 停止中...")
        self.is_running = False
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info("QuantBot 已停止")
    
    def get_status(self) -> Dict:
        stats = {'total_trades': 0, 'win_rate': 0, 'total_pnl': 0, 'positions': 0}
        if self.smart_trader:
            stats = self.smart_trader.get_performance_stats()
        
        return {
            'running': self.is_running,
            'strategies': len(self.strategies),
            'total_trades': stats.get('total_trades', 0),
            'win_rate': stats.get('win_rate', 0),
            'total_pnl': stats.get('total_pnl', 0),
            'positions': len(self.smart_trader.get_open_positions()) if self.smart_trader else 0,
        }