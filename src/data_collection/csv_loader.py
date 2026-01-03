"""
CSV data loader for SAP production orders
"""
import pandas as pd
from pathlib import Path
from loguru import logger
from typing import Optional


class CSVLoader:
    """Load and validate SAP CSV exports"""
    
    def __init__(self, data_dir: str = "data/raw"):
        self.data_dir = Path(data_dir)
    
    def load_production_orders(self, filename: str = "production_orders.csv") -> pd.DataFrame:
        """
        Load production orders from CSV
        
        Expected columns:
        - order_id: Production order number
        - material_id: Material number
        - plant: Plant code
        - order_type: Order type
        - planned_start: Planned start date
        - planned_finish: Planned finish date
        - actual_finish: Actual finish date (for training)
        - planned_qty: Planned quantity
        - status: Order status
        - priority: Priority level
        """
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"CSV file not found: {filepath}")
        
        logger.info(f"Loading production orders from {filepath}")
        
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # Convert date columns
        date_columns = ['planned_start', 'planned_finish', 'actual_finish']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        logger.info(f"Loaded {len(df)} production orders")
        
        return df
    
    def load_material_master(self, filename: str = "material_master.csv") -> Optional[pd.DataFrame]:
        """Load material master data if available"""
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            logger.warning(f"Material master file not found: {filepath}")
            return None
        
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        logger.info(f"Loaded {len(df)} material records")
        
        return df
    
    def load_work_centers(self, filename: str = "work_centers.csv") -> Optional[pd.DataFrame]:
        """Load work center data if available"""
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            logger.warning(f"Work centers file not found: {filepath}")
            return None
        
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        logger.info(f"Loaded {len(df)} work center records")
        
        return df
    
    def validate_orders(self, df: pd.DataFrame) -> tuple[bool, list[str]]:
        """
        Validate production orders data
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        # Check required columns
        required_cols = [
            'order_id', 'material_id', 'plant', 
            'planned_start', 'planned_finish'
        ]
        
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")
        
        # Check for null values in key columns
        if 'order_id' in df.columns and df['order_id'].isnull().any():
            errors.append("Found null values in order_id column")
        
        # Check date logic
        if 'planned_start' in df.columns and 'planned_finish' in df.columns:
            invalid_dates = df[df['planned_finish'] < df['planned_start']]
            if len(invalid_dates) > 0:
                errors.append(f"Found {len(invalid_dates)} orders with finish before start")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("Data validation passed")
        else:
            logger.error(f"Data validation failed: {errors}")
        
        return is_valid, errors
