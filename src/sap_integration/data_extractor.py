"""
SAP Data Extractor
SAP 数据提取器 - 协调客户端和转换器，完成完整的数据提取流程
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict
from loguru import logger

from .sap_client import SAPODataClient
from .data_transformer import SAPDataTransformer
from .exceptions import SAPDataError


class SAPDataExtractor:
    """SAP 数据提取器"""
    
    def __init__(self, config: Dict):
        """
        初始化提取器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.client = SAPODataClient(config)
        self.transformer = SAPDataTransformer()
        
        self.output_dir = Path(config['sync']['output']['directory'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.last_sync_file = Path(config['sync']['incremental']['last_sync_file'])
    
    def extract_all_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        mode: str = 'full'
    ) -> Dict[str, pd.DataFrame]:
        """
        提取所有数据
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            mode: 同步模式 (full / incremental)
            
        Returns:
            包含所有数据的字典 {history, material, capacity}
        """
        logger.info("=" * 60)
        logger.info("开始 SAP 数据提取")
        logger.info(f"模式: {mode}, 日期范围: {start_date} - {end_date}")
        logger.info("=" * 60)
        
        # 确定日期范围
        if mode == 'incremental':
            start_date = self._get_last_sync_date()
            logger.info(f"增量同步，从 {start_date} 开始")
        elif not start_date:
            start_date = self.config['sync']['full_sync_start_date']
        
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # 1. 提取生产订单历史
        logger.info("\n步骤 1/3: 提取生产订单历史")
        try:
            orders_raw = self.client.get_all_production_orders(
                start_date=start_date,
                end_date=end_date,
                batch_size=self.config['sync']['pagination']['batch_size']
            )
            
            df_history = self.transformer.transform_production_orders(orders_raw)
            
            if self.config['sync']['validation']['enabled']:
                if not self.transformer.validate_data(df_history, 'history'):
                    raise SAPDataError("生产订单数据验证失败")
            
        except Exception as e:
            logger.error(f"提取生产订单失败: {e}")
            raise
        
        # 2. 提取物料主数据
        logger.info("\n步骤 2/3: 提取物料主数据")
        try:
            materials_raw = self.client.get_material_master()
            df_material = self.transformer.transform_material_master(materials_raw)
            
            if self.config['sync']['validation']['enabled']:
                if not self.transformer.validate_data(df_material, 'material'):
                    raise SAPDataError("物料数据验证失败")
                    
        except Exception as e:
            logger.error(f"提取物料主数据失败: {e}")
            raise
        
        # 3. 提取产线产能
        logger.info("\n步骤 3/3: 提取产线产能")
        try:
            capacity_raw = self.client.get_line_capacity()
            df_capacity = self.transformer.transform_line_capacity(capacity_raw)
            
            if self.config['sync']['validation']['enabled']:
                if not self.transformer.validate_data(df_capacity, 'capacity'):
                    raise SAPDataError("产能数据验证失败")
                    
        except Exception as e:
            logger.error(f"提取产线产能失败: {e}")
            raise
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ 数据提取完成")
        logger.info(f"  - 生产订单: {len(df_history)} 条")
        logger.info(f"  - 物料数据: {len(df_material)} 条")
        logger.info(f"  - 产能数据: {len(df_capacity)} 条")
        logger.info("=" * 60)
        
        return {
            'history': df_history,
            'material': df_material,
            'capacity': df_capacity
        }
    
    def save_to_csv(self, data: Dict[str, pd.DataFrame]):
        """
        保存数据为 CSV 文件
        
        Args:
            data: 数据字典
        """
        logger.info("保存数据到 CSV 文件")
        
        file_mapping = self.config['sync']['output']['files']
        encoding = self.config['sync']['output']['encoding']
        
        # 保存 History.csv
        if 'history' in data:
            history_path = self.output_dir / file_mapping['history']
            data['history'].to_csv(history_path, index=False, encoding=encoding)
            logger.info(f"✓ 保存 History.csv: {len(data['history'])} 行")
        
        # 保存 FG.csv
        if 'material' in data:
            fg_path = self.output_dir / file_mapping['fg']
            data['material'].to_csv(fg_path, index=False, encoding=encoding)
            logger.info(f"✓ 保存 FG.csv: {len(data['material'])} 行")
        
        # 保存 Capacity.csv
        if 'capacity' in data:
            capacity_path = self.output_dir / file_mapping['capacity']
            data['capacity'].to_csv(capacity_path, index=False, encoding=encoding)
            logger.info(f"✓ 保存 Capacity.csv: {len(data['capacity'])} 行")
        
        # 更新同步时间戳
        self._update_last_sync_date()
    
    def _get_last_sync_date(self) -> str:
        """
        获取上次同步日期
        
        Returns:
            日期字符串 (YYYY-MM-DD)
        """
        if self.last_sync_file.exists():
            with open(self.last_sync_file, 'r') as f:
                last_sync = f.read().strip()
                
            # 回溯几天以防遗漏
            lookback_days = self.config['sync']['incremental']['lookback_days']
            last_date = datetime.fromisoformat(last_sync)
            start_date = last_date - timedelta(days=lookback_days)
            
            return start_date.strftime('%Y-%m-%d')
        else:
            # 首次同步，使用配置的起始日期
            return self.config['sync']['full_sync_start_date']
    
    def _update_last_sync_date(self):
        """更新最后同步时间"""
        with open(self.last_sync_file, 'w') as f:
            f.write(datetime.now().isoformat())
        
        logger.info(f"✓ 更新同步时间戳: {datetime.now()}")
    
    def sync(self, mode: str = 'incremental') -> Dict[str, pd.DataFrame]:
        """
        执行数据同步
        
        Args:
            mode: 同步模式 (full / incremental)
            
        Returns:
            提取的数据
        """
        logger.info(f"开始 {mode} 模式数据同步")
        
        # 提取数据
        data = self.extract_all_data(mode=mode)
        
        # 保存数据
        self.save_to_csv(data)
        
        logger.info("✓ 数据同步完成")
        
        return data
