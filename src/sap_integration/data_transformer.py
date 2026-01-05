"""
SAP Data Transformer
SAP 数据转换器 - 将 SAP OData 响应转换为模型所需格式
"""
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger
import re


class SAPDataTransformer:
    """SAP 数据转换器"""
    
    @staticmethod
    def convert_sap_date(sap_date: str) -> str:
        """
        转换 SAP OData 日期格式
        
        SAP 格式: /Date(1704153600000)/
        目标格式: 2024-01-02
        
        Args:
            sap_date: SAP 日期字符串
            
        Returns:
            YYYY-MM-DD 格式日期
        """
        if not sap_date or sap_date == 'null':
            return None
        
        try:
            # 提取时间戳
            match = re.search(r'/Date\((\d+)\)/', sap_date)
            if match:
                timestamp = int(match.group(1)) / 1000  # 毫秒转秒
                dt = datetime.fromtimestamp(timestamp)
                return dt.strftime('%Y-%m-%d')
            else:
                # 尝试直接解析
                return pd.to_datetime(sap_date).strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"日期转换失败: {sap_date}, {e}")
            return None
    
    @staticmethod
    def remove_leading_zeros(value: str) -> str:
        """
        去除前导零
        
        SAP 物料号: 000000000CDX6090704R5001
        目标格式: CDX6090704R5001
        
        Args:
            value: 原始值
            
        Returns:
            去除前导零后的值
        """
        if not value:
            return value
        
        return value.lstrip('0') or '0'
    
    def transform_production_orders(self, sap_data: List[Dict]) -> pd.DataFrame:
        """
        转换生产订单数据为 History.csv 格式
        
        Args:
            sap_data: SAP OData 响应数据
            
        Returns:
            DataFrame (History.csv 格式)
        """
        logger.info(f"转换 {len(sap_data)} 条生产订单数据")
        
        transformed = []
        
        for order in sap_data:
            try:
                row = {
                    'Sales Order': self.remove_leading_zeros(order.get('SalesOrder', '')),
                    'Sales Order Item': order.get('SalesOrderItem', ''),
                    'Order': self.remove_leading_zeros(order.get('OrderNumber', '')),
                    'Material Number': self.remove_leading_zeros(order.get('MaterialNumber', '')),
                    'Material description': order.get('MaterialDescription', ''),
                    'System Status': order.get('SystemStatus', ''),
                    'Order quantity (GMEIN)': float(order.get('OrderQuantity', 0)),
                    'Confirmed quantity (GMEIN)': float(order.get('ConfirmedQuantity', 0)),
                    'Basic start date': self.convert_sap_date(order.get('BasicStartDate')),
                    'Basic finish date': self.convert_sap_date(order.get('BasicFinishDate')),
                    'Actual finish date': self.convert_sap_date(order.get('ActualFinishDate')),
                    'Unit of measure (=GMEIN)': order.get('UnitOfMeasure', ''),
                    'Created on': self.convert_sap_date(order.get('CreatedOn')),
                    'Entered by': order.get('EnteredBy', ''),
                    'Prodn Supervisor': order.get('ProductionSupervisor', ''),
                    'MRP controller': order.get('MRPController', '')
                }
                
                transformed.append(row)
                
            except Exception as e:
                logger.warning(f"转换订单失败: {order.get('OrderNumber')}, {e}")
                continue
        
        df = pd.DataFrame(transformed)
        logger.info(f"✓ 成功转换 {len(df)} 条订单")
        
        return df
    
    def transform_material_master(self, sap_data: List[Dict]) -> pd.DataFrame:
        """
        转换物料主数据为 FG.csv 格式
        
        Args:
            sap_data: SAP OData 响应数据
            
        Returns:
            DataFrame (FG.csv 格式)
        """
        logger.info(f"转换 {len(sap_data)} 条物料数据")
        
        transformed = []
        
        for material in sap_data:
            try:
                row = {
                    'Production Line': material.get('ProductionLine', ''),
                    'Material': self.remove_leading_zeros(material.get('MaterialNumber', '')),
                    'Material Description': material.get('MaterialDescription', ''),
                    'Constraint': int(material.get('ConstraintFactor', 0)),
                    'earlist strart date': int(material.get('EarliestStartDays', 0)),
                    'Total production Time': float(material.get('TotalProductionTime', 0))
                }
                
                transformed.append(row)
                
            except Exception as e:
                logger.warning(f"转换物料失败: {material.get('MaterialNumber')}, {e}")
                continue
        
        df = pd.DataFrame(transformed)
        logger.info(f"✓ 成功转换 {len(df)} 条物料")
        
        return df
    
    def transform_line_capacity(self, sap_data: List[Dict]) -> pd.DataFrame:
        """
        转换产线产能数据为 Capacity.csv 格式
        
        Args:
            sap_data: SAP OData 响应数据
            
        Returns:
            DataFrame (Capacity.csv 格式)
        """
        logger.info(f"转换 {len(sap_data)} 条产能数据")
        
        transformed = []
        
        for capacity in sap_data:
            try:
                row = {
                    'Production Line': capacity.get('ProductionLine', ''),
                    'Capacity': int(capacity.get('LineCapacity', 0))
                }
                
                transformed.append(row)
                
            except Exception as e:
                logger.warning(f"转换产能失败: {capacity.get('ProductionLine')}, {e}")
                continue
        
        df = pd.DataFrame(transformed)
        logger.info(f"✓ 成功转换 {len(df)} 条产能数据")
        
        return df
    
    def validate_data(self, df: pd.DataFrame, data_type: str) -> bool:
        """
        验证数据质量
        
        Args:
            df: 数据 DataFrame
            data_type: 数据类型 (history / material / capacity)
            
        Returns:
            是否通过验证
        """
        logger.info(f"验证 {data_type} 数据质量")
        
        if df.empty:
            logger.error("数据为空")
            return False
        
        # 根据数据类型检查必需字段
        required_fields = {
            'history': ['Order', 'Material Number', 'Basic start date', 'Basic finish date', 'Actual finish date'],
            'material': ['Material', 'Production Line', 'Total production Time'],
            'capacity': ['Production Line', 'Capacity']
        }
        
        if data_type in required_fields:
            missing = [col for col in required_fields[data_type] if col not in df.columns]
            if missing:
                logger.error(f"缺少必需字段: {missing}")
                return False
            
            # 检查空值
            for col in required_fields[data_type]:
                null_count = df[col].isna().sum()
                if null_count > 0:
                    logger.warning(f"字段 '{col}' 有 {null_count} 个空值")
        
        logger.info(f"✓ 数据验证通过: {len(df)} 行")
        return True
