"""配置管理模組"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            base_dir = Path(__file__).parent.parent.parent
            config_path = base_dir / "config" / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load()
    
    def _load(self):
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        self._resolve_env_vars()
    
    def _resolve_env_vars(self):
        def resolve_value(value):
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                return os.getenv(env_var, '')
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            return value
        
        self._config = resolve_value(self._config)
    
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    @property
    def exchange(self) -> Dict[str, Any]:
        return self._config.get('exchange', {})
    
    @property
    def trading(self) -> Dict[str, Any]:
        return self._config.get('trading', {})
    
    @property
    def strategy(self) -> Dict[str, Any]:
        return self._config.get('strategy', {})
    
    @property
    def risk(self) -> Dict[str, Any]:
        return self._config.get('risk', {})
    
    @property
    def notification(self) -> Dict[str, Any]:
        return self._config.get('notification', {})
    
    @property
    def logging(self) -> Dict[str, Any]:
        return self._config.get('logging', {})


config = Config()