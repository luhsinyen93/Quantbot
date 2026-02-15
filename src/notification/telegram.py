"""Telegram 通知模組"""

import asyncio
import requests
from datetime import datetime

from ..core.config import config
from ..core.logger import get_logger

logger = get_logger(__name__)


class TelegramNotifier:
    def __init__(self):
        self.config = config.notification.get('telegram', {})
        self.enabled = self.config.get('enabled', False)
        self.bot_token = self.config.get('bot_token', '')
        self.chat_id = self.config.get('chat_id', '')
        
        self.last_send_time = 0
        
        if self.enabled:
            logger.info(f"Telegram 通知已啟用: chat_id={self.chat_id}")
    
    def _send_message(self, text: str) -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        payload = {'chat_id': self.chat_id, 'text': text, 'parse_mode': 'Markdown'}
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.json().get('ok', False)
        except Exception as e:
            logger.error(f"Telegram 發送錯誤: {e}")
            return False
    
    async def send(self, text: str) -> bool:
        return await asyncio.to_thread(self._send_message, text)
    
    async def notify_entry(self, symbol: str, side: str, price: float, quantity: float, reason: str):
        emoji = "🟢" if side.upper() == "BUY" else "🔴"
        
        text = f"""
{emoji} *進場通知*

📌 交易對: {symbol}
📍 方向: {side.upper()}
💰 價格: {price:,.4f}

🤖 原因: {reason}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.send(text)
    
    async def notify_exit(self, symbol: str, pnl: float, pnl_pct: float, reason: str):
        emoji = "✅" if pnl > 0 else "❌"
        
        text = f"""
{emoji} *退場通知*

📌 交易對: {symbol}
📈 盈虧: {pnl:+.2f} USDT ({pnl_pct:+.2f}%)
📝 理由: {reason}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.send(text)
    
    async def notify_error(self, error_type: str, message: str):
        text = f"""
⚠️ *錯誤警報*

❌ 類型: {error_type}
📝 訊息: {message}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        await self.send(text)


notifier = TelegramNotifier()