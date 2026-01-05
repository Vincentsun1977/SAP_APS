"""
APS Data Loader - Merges Order, FG, Capacity, APS, and History CSV files
"""
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger
from typing import Tuple, Optional


class APSDataLoader:
    """Load and merge APS system data files"""
    
    def __init__(self, data_dir: str = "data/raw"):
        """
        Initialize data loader
        
        Args:
            data_dir: Directory containing CSV files
        """
        self.data_dir = Path(data_dir)
        self.order_df = None
        self.fg_df = None
        self.capacity_df = None
        self.aps_df = None
        self.history_df = None
        
    def load_all_files(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Load all 5 CSV files
        
        Returns:
            Tuple of (order, fg, capacity, aps, history) DataFrames
        """
        logger.info("Loading CSV files...")
        
        # Load Order.csv
        order_path = self.data_dir / "Order.csv"
        self.order_df = pd.read_csv(order_path, encoding='utf-8')
        logger.info(f"✓ Loaded Order.csv: {len(self.order_df)} rows")
        
        # Load FG.csv
        fg_path = self.data_dir / "FG.csv"
        self.fg_df = pd.read_csv(fg_path, encoding='utf-8')
        logger.info(f"✓ Loaded FG.csv: {len(self.fg_df)} rows")
        
        # Load Capacity.csv
        capacity_path = self.data_dir / "Capacity.csv"
        self.capacity_df = pd.read_csv(capacity_path, encoding='utf-8')
        logger.info(f"✓ Loaded Capacity.csv: {len(self.capacity_df)} rows")
        
        # Load APS.csv
        aps_path = self.data_dir / "APS.csv"
        self.aps_df = pd.read_csv(aps_path, encoding='utf-8')
        logger.info(f"✓ Loaded APS.csv: {len(self.aps_df)} rows")
        
        # Load History.csv
        history_path = self.data_dir / "History.csv"
        self.history_df = pd.read_csv(history_path, encoding='utf-8')
        logger.info(f"✓ Loaded History.csv: {len(self.history_df)} rows")
        
        return self.order_df, self.fg_df, self.capacity_df, self.aps_df, self.history_df
    
    def preprocess_history(self) -> pd.DataFrame:
        """
        Preprocess historical data
        
        Returns:
            Cleaned history DataFrame
        """
        logger.info("Preprocessing History.csv...")
        
        df = self.history_df.copy()
        
        # Rename columns to standard names
        column_mapping = {
            'Sales Order': 'sales_doc',
            'Sales Order Item': 'item',
            'Order': 'production_number',
            'Material Number': 'material',
            'Material description': 'material_description',
            'System Status': 'system_status',
            'Order quantity (GMEIN)': 'order_quantity',
            'Confirmed quantity (GMEIN)': 'confirmed_quantity',
            'Basic start date': 'planned_start_date',
            'Basic finish date': 'planned_finish_date',
            'Actual finish date': 'actual_finish_date',
            'Unit of measure (=GMEIN)': 'unit',
            'Created on': 'created_date',
            'Entered by': 'entered_by',
            'Prodn Supervisor': 'production_supervisor',
            'MRP controller': 'mrp_controller'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Convert date columns
        date_cols = ['planned_start_date', 'planned_finish_date', 'actual_finish_date', 'created_date']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Filter only completed orders (with actual finish date)
        df_completed = df[df['actual_finish_date'].notna()].copy()
        logger.info(f"Completed orders: {len(df_completed)} / {len(df)}")
        
        # Calculate delay
        df_completed['planned_duration_days'] = (
            df_completed['planned_finish_date'] - df_completed['planned_start_date']
        ).dt.days
        
        df_completed['actual_duration_days'] = (
            df_completed['actual_finish_date'] - df_completed['planned_start_date']
        ).dt.days
        
        df_completed['delay_days'] = (
            df_completed['actual_finish_date'] - df_completed['planned_finish_date']
        ).dt.days
        
        # Binary delay flag (1 if delayed, 0 if on-time or early)
        df_completed['is_delayed'] = (df_completed['delay_days'] > 0).astype(int)
        
        logger.info(f"Delay distribution - Delayed: {df_completed['is_delayed'].sum()}, "
                   f"On-time: {len(df_completed) - df_completed['is_delayed'].sum()}")
        logger.info(f"Average delay: {df_completed['delay_days'].mean():.2f} days")
        
        return df_completed
    
    def merge_with_fg_data(self, history_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merge history with FG master data
        
        Args:
            history_df: Preprocessed history DataFrame
            
        Returns:
            Merged DataFrame with FG information
        """
        logger.info("Merging with FG master data...")
        
        # Clean FG column names
        fg_df = self.fg_df.copy()
        fg_df.columns = fg_df.columns.str.strip()
        
        # Rename FG columns
        # Note: 'Constraint' in FG.csv = daily production capacity (units/day) for material on line
        fg_mapping = {
            'Production Line': 'production_line',
            'Material': 'material',
            'Material Description': 'fg_material_description',
            'Constraint': 'constraint_factor',  # Daily capacity (units/day)
            'earlist strart date': 'earliest_start_days',
            'Total production Time': 'total_production_time'  # Hours per unit
        }
        fg_df = fg_df.rename(columns=fg_mapping)
        
        # Merge on material
        merged = history_df.merge(
            fg_df[['material', 'production_line', 'constraint_factor', 'earliest_start_days', 'total_production_time']],
            on='material',
            how='left'
        )
        
        logger.info(f"Merged with FG data: {len(merged)} rows")
        logger.info(f"Missing FG data: {merged['production_line'].isna().sum()} rows")
        
        return merged
    
    def merge_with_capacity(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merge with production line capacity
        
        Args:
            merged_df: DataFrame already merged with FG
            
        Returns:
            DataFrame with capacity information
        """
        logger.info("Merging with capacity data...")
        
        # Clean capacity column names
        capacity_df = self.capacity_df.copy()
        capacity_df.columns = capacity_df.columns.str.strip()
        
        capacity_mapping = {
            'Production Line': 'production_line',
            'Capacity': 'line_capacity'
        }
        capacity_df = capacity_df.rename(columns=capacity_mapping)
        
        # Merge on production line
        merged = merged_df.merge(
            capacity_df,
            on='production_line',
            how='left'
        )
        
        logger.info(f"Merged with capacity data: {len(merged)} rows")
        
        return merged
    
    def load_and_merge(self) -> pd.DataFrame:
        """
        Main pipeline: load all files and create unified training dataset
        
        Returns:
            Final merged DataFrame ready for feature engineering
        """
        logger.info("=" * 60)
        logger.info("APS Data Loading Pipeline")
        logger.info("=" * 60)
        
        # Step 1: Load all files
        self.load_all_files()
        
        # Step 2: Process history (main training data)
        history_clean = self.preprocess_history()
        
        # Step 3: Merge with FG master data
        merged = self.merge_with_fg_data(history_clean)
        
        # Step 4: Merge with capacity
        merged = self.merge_with_capacity(merged)
        
        # Step 5: Create additional features
        merged = self._create_basic_features(merged)
        
        logger.info("=" * 60)
        logger.info(f"✓ Final dataset: {len(merged)} rows × {len(merged.columns)} columns")
        logger.info(f"✓ Training samples: {merged['is_delayed'].notna().sum()}")
        logger.info(f"✓ Delay rate: {merged['is_delayed'].mean():.2%}")
        logger.info("=" * 60)
        
        return merged
    
    def _create_basic_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create basic derived features
        
        Args:
            df: Merged DataFrame
            
        Returns:
            DataFrame with additional features
        """
        logger.info("Creating basic features...")
        
        # Convert numeric columns to proper types
        df['order_quantity'] = pd.to_numeric(df['order_quantity'], errors='coerce')
        df['line_capacity'] = pd.to_numeric(df['line_capacity'], errors='coerce')
        df['total_production_time'] = pd.to_numeric(df['total_production_time'], errors='coerce')
        # rename and coerce constraint_factor from FG to numeric
        if 'constraint' in df.columns and 'constraint_factor' not in df.columns:
            df['constraint_factor'] = df['constraint']
        df['constraint_factor'] = pd.to_numeric(df['constraint_factor'], errors='coerce')
        df['earliest_start_days'] = pd.to_numeric(df['earliest_start_days'], errors='coerce')
        
        # Quantity vs capacity ratio
        df['qty_capacity_ratio'] = df['order_quantity'] / df['line_capacity']
        
        # Expected production days based on FG time
        df['expected_production_days'] = (
            df['order_quantity'] * df['total_production_time'] / df['line_capacity']
        )
        
        # Time features
        df['planned_start_month'] = df['planned_start_date'].dt.month
        df['planned_start_weekday'] = df['planned_start_date'].dt.weekday
        df['planned_start_quarter'] = df['planned_start_date'].dt.quarter
        df['planned_start_year'] = df['planned_start_date'].dt.year
        
        # Whether production supervisor is assigned
        df['has_supervisor'] = df['production_supervisor'].notna().astype(int)
        
        return df
    
    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, list]:
        """
        Validate merged dataset
        
        Args:
            df: Merged DataFrame
            
        Returns:
            Tuple of (is_valid, errors_list)
        """
        errors = []
        
        # Check required columns
        required_cols = [
            'production_number', 'material', 'order_quantity',
            'planned_start_date', 'planned_finish_date', 'actual_finish_date',
            'production_line', 'line_capacity', 'is_delayed'
        ]
        
        for col in required_cols:
            if col not in df.columns:
                errors.append(f"Missing required column: {col}")
        
        # Check for null values in critical columns
        critical_cols = ['material', 'order_quantity', 'is_delayed']
        for col in critical_cols:
            if col in df.columns:
                null_count = df[col].isna().sum()
                if null_count > 0:
                    errors.append(f"Column '{col}' has {null_count} null values")
        
        # Check delay calculation
        if 'is_delayed' in df.columns:
            if df['is_delayed'].isna().all():
                errors.append("All delay labels are null")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("✓ Data validation passed")
        else:
            logger.error(f"✗ Data validation failed with {len(errors)} errors")
            for err in errors:
                logger.error(f"  - {err}")
        
        return is_valid, errors
    
    def save_processed_data(self, df: pd.DataFrame, output_path: str = "data/processed/training_data.csv"):
        """
        Save processed data to CSV
        
        Args:
            df: Processed DataFrame
            output_path: Output file path
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(output_file, index=False, encoding='utf-8')
        logger.info(f"✓ Saved processed data to {output_path}")


if __name__ == "__main__":
    # Test the loader
    loader = APSDataLoader("data/raw")
    df = loader.load_and_merge()
    
    # Validate
    is_valid, errors = loader.validate_data(df)
    
    if is_valid:
        # Save processed data
        loader.save_processed_data(df)
        
        # Print summary
        print("\n" + "=" * 60)
        print("DATA SUMMARY")
        print("=" * 60)
        print(f"Total records: {len(df)}")
        print(f"Date range: {df['planned_start_date'].min()} to {df['planned_start_date'].max()}")
        print(f"\nDelay Statistics:")
        print(f"  - Delayed orders: {df['is_delayed'].sum()} ({df['is_delayed'].mean():.1%})")
        print(f"  - On-time orders: {len(df) - df['is_delayed'].sum()}")
        print(f"  - Average delay: {df['delay_days'].mean():.2f} days")
        print(f"  - Max delay: {df['delay_days'].max():.0f} days")
        print(f"\nTop 5 Materials by Volume:")
        print(df.groupby('material')['order_quantity'].sum().sort_values(ascending=False).head())
        print("=" * 60)
    else:
        print("\n❌ Data validation failed!")
        for err in errors:
            print(f"  - {err}")
