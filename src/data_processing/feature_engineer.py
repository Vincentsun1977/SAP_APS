"""
Feature engineering for production order prediction
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger


class FeatureEngineer:
    """Generate features for XGBoost model"""
    
    def __init__(self, lookback_days: int = 30):
        self.lookback_days = lookback_days
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all feature transformations
        
        Args:
            df: Raw production orders DataFrame
            
        Returns:
            DataFrame with engineered features
        """
        logger.info("Starting feature engineering")
        
        df = df.copy()
        
        # Time-based features
        df = self._create_time_features(df)
        
        # Order-based features
        df = self._create_order_features(df)
        
        # Historical features
        df = self._create_historical_features(df)
        
        # Target variable (for training)
        if 'actual_finish' in df.columns:
            df = self._create_target(df)
        
        logger.info(f"Feature engineering complete. Total features: {len(df.columns)}")
        
        return df
    
    def _create_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create time-related features"""
        logger.debug("Creating time features")
        
        # Planned duration
        df['planned_duration_days'] = (
            df['planned_finish'] - df['planned_start']
        ).dt.days
        
        # Days until start
        df['days_until_start'] = (
            df['planned_start'] - pd.Timestamp.now()
        ).dt.days
        
        # Temporal features
        df['start_month'] = df['planned_start'].dt.month
        df['start_weekday'] = df['planned_start'].dt.weekday
        df['start_quarter'] = df['planned_start'].dt.quarter
        
        # Is holiday season (example: Dec-Jan)
        df['is_holiday_season'] = df['start_month'].isin([12, 1]).astype(int)
        
        return df
    
    def _create_order_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create order-specific features"""
        logger.debug("Creating order features")
        
        # Encode categorical variables
        df['order_type_encoded'] = pd.Categorical(df['order_type']).codes
        
        # Priority (normalize)
        if 'priority' in df.columns:
            df['priority_normalized'] = df['priority'] / df['priority'].max()
        
        # Quantity-based features
        if 'planned_qty' in df.columns:
            df['log_planned_qty'] = np.log1p(df['planned_qty'])
        
        return df
    
    def _create_historical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create historical statistics features
        
        Note: For first run with no history, these will be 0/nan
        """
        logger.debug("Creating historical features")
        
        # Material delay rate in past 30 days
        df['material_delay_rate_30d'] = df.groupby('material_id').apply(
            lambda x: self._calc_delay_rate(x, self.lookback_days)
        ).reset_index(level=0, drop=True)
        
        # Plant delay rate
        df['plant_delay_rate_30d'] = df.groupby('plant').apply(
            lambda x: self._calc_delay_rate(x, self.lookback_days)
        ).reset_index(level=0, drop=True)
        
        # Fill NaN with 0 for first-time materials/plants
        df['material_delay_rate_30d'].fillna(0, inplace=True)
        df['plant_delay_rate_30d'].fillna(0, inplace=True)
        
        return df
    
    def _calc_delay_rate(self, group: pd.DataFrame, days: int) -> float:
        """
        Calculate delay rate for a group
        
        Args:
            group: Grouped DataFrame
            days: Lookback period
            
        Returns:
            Delay rate (0-1)
        """
        cutoff_date = pd.Timestamp.now() - timedelta(days=days)
        
        # Filter to recent orders with actual finish date
        recent = group[
            (group['planned_start'] >= cutoff_date) &
            (group['actual_finish'].notna())
        ]
        
        if len(recent) == 0:
            return 0.0
        
        # Count delayed orders
        delayed = (recent['actual_finish'] > recent['planned_finish']).sum()
        
        return delayed / len(recent)
    
    def _create_target(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create target variable (binary classification)
        
        Target: 1 if delayed, 0 if on-time
        """
        logger.debug("Creating target variable")
        
        df['is_delayed'] = (
            df['actual_finish'] > df['planned_finish']
        ).astype(int)
        
        logger.info(f"Target distribution - Delayed: {df['is_delayed'].sum()}, "
                   f"On-time: {(~df['is_delayed'].astype(bool)).sum()}")
        
        return df
    
    def get_feature_names(self) -> list[str]:
        """Return list of feature column names (excluding target and IDs)"""
        return [
            # Time features
            'planned_duration_days',
            'days_until_start',
            'start_month',
            'start_weekday',
            'start_quarter',
            'is_holiday_season',
            
            # Order features
            'order_type_encoded',
            'priority_normalized',
            'log_planned_qty',
            
            # Historical features
            'material_delay_rate_30d',
            'plant_delay_rate_30d',
        ]
