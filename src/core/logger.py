"""日誌系統"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from ..core.config import config


class Logger:
    _instance: Optional[logging.Logger] = None
    
    @classmethod
    def get_logger(cls, name: str = "QuantBot") -> logging.Logger:
        if cls._instance is not None:
            return cls._instance.getChild(name)
        
        root_logger = logging.getLogger("QuantBot")
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers.clear()
        
        log_config = config.logging
        level = getattr(logging, log_config.get('level', 'INFO'))
        log_file = log_config.get('file', 'logs/quantbot.log')
        max_size = log_config.get('max_size', 10) * 1024 * 1024
        console = log_config.get('console', True)
        
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_size, backupCount=5, encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        cls._instance = root_logger
        return root_logger.getChild(name)


def get_logger(name: str = __name__) -> logging.Logger:
    return Logger.get_logger(name)