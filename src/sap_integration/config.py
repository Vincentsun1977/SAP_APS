"""
Configuration loader for SAP integration
SAP 集成配置加载器
"""
import yaml
import os
from pathlib import Path
from typing import Dict, Any
from loguru import logger
from dotenv import load_dotenv


class SAPConfig:
    """SAP 配置管理器"""
    
    def __init__(self, config_file: str = "config/sap_config.yaml"):
        """
        加载配置
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = Path(config_file)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载 YAML 配置文件"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_file}")
        
        # 加载环境变量
        load_dotenv()
        
        # 读取 YAML
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 替换环境变量
        config = self._replace_env_vars(config)
        
        logger.info(f"✓ 配置加载成功: {self.config_file}")
        
        return config
    
    def _replace_env_vars(self, config: Any) -> Any:
        """
        递归替换配置中的环境变量
        
        ${VAR_NAME} -> 环境变量值
        
        Args:
            config: 配置对象
            
        Returns:
            替换后的配置
        """
        if isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        elif isinstance(config, str):
            # 检查是否是环境变量引用
            if config.startswith('${') and config.endswith('}'):
                var_name = config[2:-1]
                value = os.getenv(var_name)
                if value is None:
                    logger.warning(f"环境变量未设置: {var_name}")
                    return config
                return value
            return config
        else:
            return config
    
    def get(self, key: str = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键（支持点号分隔，如 'sap.host'）
            
        Returns:
            配置值
        """
        if key is None:
            return self.config
        
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
    
    def validate(self) -> bool:
        """
        验证配置完整性
        
        Returns:
            配置是否有效
        """
        required_keys = [
            'sap.host',
            'sap.port',
            'sap.client',
            'sap.auth.username',
            'sap.auth.password',
            'sap.services.production_orders'
        ]
        
        for key in required_keys:
            value = self.get(key)
            if value is None or (isinstance(value, str) and value.startswith('${')):
                logger.error(f"配置缺失或环境变量未设置: {key}")
                return False
        
        logger.info("✓ 配置验证通过")
        return True
