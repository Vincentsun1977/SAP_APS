"""
Feature engineering for APS production order prediction
Updated to work with new data structure from History.csv + FG.csv + Capacity.csv
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger


class APSFeatureEngineer:
    """Generate features for XGBoost model from APS data"""
    
    def __init__(self, lookback_days: int = 90):
        """
        Initialize feature engineer
        
        Args:
            lookback_days: Days to look back for historical features
        """
        self.lookback_days = lookback_days
        self.feature_names = None
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all feature transformations
        
        Args:
            df: Merged production orders DataFrame from APSDataLoader
            
        Returns:
            DataFrame with engineered features
        """
        logger.info("Starting APS feature engineering")
        
        df = df.copy()
        
        # Additional time-based features (basic ones already created in loader)
        df = self._create_advanced_time_features(df)
        
        # Material-based features
        df = self._create_material_features(df)
        
        # Production line features
        df = self._create_production_line_features(df)
        
        #Historical features
        df = self._create_historical_features(df)
        
        # Interaction features
        df = self._create_interaction_features(df)
        
        logger.info(f"Feature engineering complete. Total columns: {len(df.columns)}")
        
        return df
    
    def _create_advanced_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create advanced time-related features"""
        logger.debug("Creating advanced time features")
        
        # Is weekend
        df['is_weekend'] = (df['planned_start_weekday'] >= 5).astype(int)
        
        # Is month start/end
        df['is_month_start'] = (df['planned_start_date'].dt.day <= 5).astype(int)
        df['is_month_end'] = (df['planned_start_date'].dt.day >= 25).astype(int)
        
        # Quarter end  
        df['is_quarter_end'] = df['planned_start_date'].dt.is_quarter_end.astype(int)
        
        # Year end
        df['is_year_end'] = (df['planned_start_month'] == 12).astype(int)
        
        # Week of year
        df['week_of_year'] = df['planned_start_date'].dt.isocalendar().week
        
        return df
    
    def _create_material_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create material-specific features"""
        logger.debug("Creating material features")
        
        # Log transform of quantities to handle scale
        df['log_order_quantity'] = np.log1p(df['order_quantity'])
        
        # Material family (extract from material code if pattern exists)
        # CDX6291204R5011 -> CDX629 (first 6 chars as family)
        df['material_family'] = df['material'].str[:6]
        df['material_family_encoded'] = pd.Categorical(df['material_family']).codes
        
        # Product type indicator (ConVac vs VSC from description)
        if 'material_description' in df.columns:
            df['is_convac'] = df['material_description'].str.contains('ConVac', case=False, na=False).astype(int)
            df['is_vsc'] = df['material_description'].str.contains('VSC', case=False, na=False).astype(int)
        else:
            df['is_convac'] = 0
            df['is_vsc'] = 0
        
        return df
    
    def _create_production_line_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create production line and capacity features"""
        logger.debug("Creating production line features")
        
        # Production line encoding
        df['production_line_encoded'] = pd.Categorical(df['production_line']).codes
        
        # Capacity utilization features (already have qty_capacity_ratio and expected_production_days)
        # Add production complexity indicator
        # constraint_factor = maximum daily capacity (units/day) under full load
        # total_production_time = days required to produce one unit
        # production_complexity = simply use production time as complexity measure
        # Higher value = more complex/time-intensive product (2.5 > 2.0 = more complex)
        df['production_complexity'] = df['total_production_time']
        
        # Is large order (> 10 units)
        df['is_large_order'] = (df['order_quantity'] > 10).astype(int)
        
        # Production time category
        df['production_time_category'] = pd.cut(
            df['total_production_time'],
            bins=[0, 2, 2.5, 3, 100],
            labels=['fast', 'medium', 'slow', 'very_slow']
        )
        df['production_time_category_encoded'] = pd.Categorical(df['production_time_category']).codes
        
        return df
    
    def _create_historical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create historical performance features
        Uses rolling window to calculate historical metrics
        """
        logger.debug("Creating historical features")
        
        # Sort by date to ensure proper rolling calculations
        df = df.sort_values('planned_start_date')
        
        # Material historical delay rate (last 90 days)
        df['material_delay_rate_90d'] = df.groupby('material')['is_delayed'].transform(
            lambda x: x.rolling(window=30, min_periods=5).mean().shift(1)
        )
        df['material_delay_rate_90d'].fillna(df['is_delayed'].mean(), inplace=True)
        
        # Production line historical delay rate
        df['line_delay_rate_90d'] = df.groupby('production_line')['is_delayed'].transform(
            lambda x: x.rolling(window=30, min_periods=5).mean().shift(1)
        )
        df['line_delay_rate_90d'].fillna(df['is_delayed'].mean(), inplace=True)
        
        # Material family delay rate
        df['material_family_delay_rate'] = df.groupby('material_family')['is_delayed'].transform(
            lambda x: x.rolling(window=20, min_periods=3).mean().shift(1)
        )
        df['material_family_delay_rate'].fillna(df['is_delayed'].mean(), inplace=True)
        
        # Average historical delay days for material
        df['material_avg_delay_days'] = df.groupby('material')['delay_days'].transform(
            lambda x: x.rolling(window=20, min_periods=3).mean().shift(1)
        )
        df['material_avg_delay_days'].fillna(0, inplace=True)
        
        # Production count in last 30 days (workload indicator)
        df['material_production_count_30d'] = df.groupby('material').cumcount()
        
        return df
    
    def _create_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create interaction features between variables"""
        logger.debug("Creating interaction features")
        
        # Quantity × Production time
        df['qty_time_interaction'] = df['order_quantity'] * df['total_production_time']
        
        # Capacity ratio × Holiday indicator
        df['capacity_holiday_interaction'] = df['qty_capacity_ratio'] * (df['planned_start_month'].isin([12, 1, 2]).astype(int))
        
        # Large order × Historical delay rate
        df['large_order_history_interaction'] = df['is_large_order'] * df['material_delay_rate_90d']
        
        # Production complexity × capacity ratio
        df['complexity_capacity_interaction'] = df['production_complexity'] * df['qty_capacity_ratio']
        
        return df
    
    def get_feature_names(self) -> list:
        """Return list of feature column names for model training"""
        
        features = [
            # Basic features from loader
            'planned_duration_days',
            'order_quantity',
            'total_production_time',
            'line_capacity',
            'constraint_factor',
            'earliest_start_days',
            'qty_capacity_ratio',
            'expected_production_days',
            'planned_start_month',
            'planned_start_weekday',
            'planned_start_quarter',
            'planned_start_year',
            'has_supervisor',
            
            # Advanced time features
            'is_weekend',
            'is_month_start',
            'is_month_end',
            'is_quarter_end',
            'is_year_end',
            'week_of_year',
            
            # Material features
            'log_order_quantity',
            'material_family_encoded',
            'is_convac',
            'is_vsc',
            
            # Production line features
            'production_line_encoded',
            'production_complexity',
            'is_large_order',
            'production_time_category_encoded',
            
            # Historical features
            'material_delay_rate_90d',
            'line_delay_rate_90d',
            'material_family_delay_rate',
            'material_avg_delay_days',
            'material_production_count_30d',
            
            # Interaction features
            'qty_time_interaction',
            'capacity_holiday_interaction',
            'large_order_history_interaction',
            'complexity_capacity_interaction',
        ]
        
        return features
    
    def select_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Select and validate feature columns
        
        Args:
            df: DataFrame with all features
            
        Returns:
            DataFrame with only valid feature columns
        """
        feature_cols = self.get_feature_names()
        
        # Check which features actually exist
        available_features = [col for col in feature_cols if col in df.columns]
        missing_features = [col for col in feature_cols if col not in df.columns]
        
        if missing_features:
            logger.warning(f"Missing {len(missing_features)} features: {missing_features[:5]}...")
        
        logger.info(f"Selected {len(available_features)} features for training")
        
        return df[available_features]


if __name__ == "__main__":
    # Test with processed data
    from src.data_processing.aps_data_loader import APSDataLoader
    
    logger.info("Testing APS Feature Engineer")
    
    # Load data
    loader = APSDataLoader("data/raw")
    df = loader.load_and_merge()
    
    # Engineer features
    engineer = APSFeatureEngineer(lookback_days=90)
    df_features = engineer.transform(df)
    
    # Get feature columns
    feature_names = engineer.get_feature_names()
    
    print("\n" + "=" * 60)
    print("FEATURE ENGINEERING SUMMARY")
    print("=" * 60)
    print(f"Total features: {len(feature_names)}")
    print(f"DataFrame shape: {df_features.shape}")
    print(f"\nFeatures:")
    for i, feat in enumerate(feature_names, 1):
        if feat in df_features.columns:
            print(f"  {i:2d}. {feat:40s} ✓")
        else:
            print(f"  {i:2d}. {feat:40s} ✗ MISSING")
    
    # Select features for training
    df_selected = engineer.select_features(df_features)
    print(f"\nSelected features shape: {df_selected.shape}")
    print(f"Missing values: {df_selected.isna().sum().sum()}")
    print("=" * 60)
