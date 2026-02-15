"""QuantBot - 量化交易機器人

用法:
    python main.py              # 啟動機器人
    python main.py --status     # 查看狀態
"""

import sys
import argparse
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.bot import QuantBot
from src.core.logger import get_logger

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description='QuantBot - 量化交易機器人')
    parser.add_argument('--status', action='store_true', help='查看機器人狀態')
    parser.add_argument('--config', type=str, default='config/config.yaml', help='配置文件路徑')
    return parser.parse_args()


async def main():
    args = parse_args()
    
    if args.status:
        print("=" * 50)
        print("QuantBot 狀態")
        print("=" * 50)
        print("請運行機器人後查看即時狀態")
        return
    
    logger.info("正在啟動 QuantBot...")
    bot = QuantBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("收到中斷信號")
    except Exception as e:
        logger.error(f"發生錯誤: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())