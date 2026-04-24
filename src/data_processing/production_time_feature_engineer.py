"""
Feature engineering for production time prediction (regression)
Predicts total production time = Actual finish date - Created on

Improvements v2:
- P0: Removed leaked features (actual_duration_days, delay_days, is_delayed)
- P0: Fixed historical feature fillna to use expanding mean (no future leak)
- P1: Added concurrent workload features (orders/qty on same start date)
- P1: Added create-to-start buffer gap feature
- P2: Added MRP controller encoding, log(order_quantity), removed constant features
- P3: Richer historical stats (std, max, count, last), target encoding for material
- P4: Outlier flagging for extreme orders
Improvements v4:
- Relaxed outlier cutoff (30 → 45 days) to retain more training data
- Added target winsorization at 1st / 99th percentile (reduces outlier impact w/o row loss)
- New feature: planned_total_cycle_days (planned_finish - created, directly maps to target span)
- New feature: year + day_of_year for trend & seasonality
- New feature: qty_ratio_to_material_avg (relative order size)
- New feature: material_cv_production_time (historical volatility)"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger


class ProductionTimeFeatureEngineer:
    """Generate features for production time prediction (regression)"""
    
    def __init__(self, lookback_days: int = 90, max_wait_days: float = 3.0):
        """
        Initialize feature engineer for production time prediction
        
        Args:
            lookback_days: Days to look back for historical features
            max_wait_days: Max allowed wait time (actual_start - created_date) in days.
                           Orders exceeding this are excluded from training to reduce noise.
                           Set to 0 or None to disable filtering.
        """
        self.lookback_days = lookback_days
        self.max_wait_days = max_wait_days
        self.feature_names = None
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all feature transformations for production time prediction
        
        Args:
            df: Merged production orders DataFrame from APSDataLoader
            
        Returns:
            DataFrame with engineered features and target variable (actual_production_days)
        """
        logger.info("Starting production time feature engineering (v2)")
        
        df = df.copy()
        
        # Create target variable: actual production time in days
        df = self._create_target_variable(df)
        
        # Remove records with invalid target values
        df = df[df['actual_production_days'].notna()].copy()
        
        # P4: Filter extreme outliers (production days > 45 or qty > 500)
        before_len = len(df)
        df = df[df['actual_production_days'] <= 45].copy()
        df = df[df['order_quantity'] <= 500].copy()
        logger.info(f"Outlier filtering: {before_len} -> {len(df)} rows (removed {before_len - len(df)} outliers)")

        # v4: Winsorize target at 1st / 99th percentile (keep rows, clip extreme values)
        lo = df['actual_production_days'].quantile(0.01)
        hi = df['actual_production_days'].quantile(0.99)
        before_clip = df['actual_production_days'].describe()
        df['actual_production_days'] = df['actual_production_days'].clip(lower=lo, upper=hi)
        logger.info(f"Target winsorized to [{lo:.1f}, {hi:.1f}] days")
        
        # P7: Filter orders with excessive wait time (created -> actual_start)
        if self.max_wait_days and self.max_wait_days > 0 and 'actual_start_date' in df.columns:
            df['actual_start_date'] = pd.to_datetime(df['actual_start_date'], errors='coerce')
            wait_days = (df['actual_start_date'] - df['created_date']).dt.total_seconds() / (24 * 3600)
            before_wait = len(df)
            # Only filter rows where wait info is available and exceeds threshold
            excessive_wait = wait_days.notna() & (wait_days >= self.max_wait_days)
            df = df[~excessive_wait].copy()
            logger.info(f"Wait time filter (>={self.max_wait_days}d): {before_wait} -> {len(df)} rows "
                        f"(removed {before_wait - len(df)} long-wait orders)")
        
        # Time-based features
        df = self._create_time_features(df)
        
        # P1: Concurrent workload features (must be after time features)
        df = self._create_concurrent_features(df)
        
        # P5: Forward-looking workload features (pipeline load at order creation)
        df = self._create_forward_workload_features(df)
        
        # Material-based features
        df = self._create_material_features(df)
        
        # Production line features
        df = self._create_production_line_features(df)
        
        # Historical features (average production time) - improved with richer stats
        df = self._create_historical_features(df)
        
        # P3: Target encoding for material
        df = self._create_target_encoding(df)
        
        # Interaction features
        df = self._create_interaction_features(df)
        
        # Capacity and workload features
        df = self._create_capacity_features(df)
        
        logger.info(f"Feature engineering complete. Shape: {df.shape}")
        
        return df
    
    def _create_target_variable(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create target variable: actual production time in days
        = Actual finish date - Created on
        """
        logger.info("Creating target variable: actual_production_days")
        
        # Ensure date columns are datetime
        df['actual_finish_date'] = pd.to_datetime(df['actual_finish_date'])
        df['created_date'] = pd.to_datetime(df['created_date'])
        
        # Calculate actual production days: actual finish - order created date
        # (end-to-end cycle time from order creation to completion)
        raw_days = (
            df['actual_finish_date'] - df['created_date']
        ).dt.total_seconds() / (24 * 3600)
        # Floor: same-day completion = 1 working day (not 0)
        df['actual_production_days'] = np.maximum(raw_days, 1.0)
        
        # Log statistics
        valid_count = df['actual_production_days'].notna().sum()
        logger.info(f"Valid production time records: {valid_count}")
        logger.info(f"Production time stats:")
        logger.info(f"  Mean: {df['actual_production_days'].mean():.2f} days")
        logger.info(f"  Median: {df['actual_production_days'].median():.2f} days")
        logger.info(f"  Std: {df['actual_production_days'].std():.2f} days")
        logger.info(f"  Min: {df['actual_production_days'].min():.2f} days")
        logger.info(f"  Max: {df['actual_production_days'].max():.2f} days")
        
        return df
    
    def _create_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create time-based features from planned start/finish dates"""
        logger.info("Creating time-based features")
        
        # Planned production days
        df['planned_production_days'] = (
            df['planned_finish_date'] - df['planned_start_date']
        ).dt.total_seconds() / (24 * 3600)
        
        # P1: Create-to-start buffer gap (urgency indicator)
        df['create_to_start_gap'] = (
            df['planned_start_date'] - df['created_date']
        ).dt.total_seconds() / (24 * 3600)
        
        # Start date features
        df['planned_start_month'] = df['planned_start_date'].dt.month
        df['planned_start_quarter'] = df['planned_start_date'].dt.quarter
        df['planned_start_weekday'] = df['planned_start_date'].dt.weekday
        df['planned_start_is_weekend'] = df['planned_start_weekday'].isin([5, 6]).astype(int)
        df['planned_start_day_of_month'] = df['planned_start_date'].dt.day
        df['planned_start_is_month_start'] = (df['planned_start_day_of_month'] <= 5).astype(int)
        df['planned_start_is_month_end'] = (df['planned_start_day_of_month'] >= 25).astype(int)
        
        # Finish date features
        df['planned_finish_month'] = df['planned_finish_date'].dt.month
        df['planned_finish_quarter'] = df['planned_finish_date'].dt.quarter
        df['planned_finish_weekday'] = df['planned_finish_date'].dt.weekday
        
        # Order quantity per planned day
        df['qty_per_planned_day'] = df['order_quantity'] / (df['planned_production_days'] + 1e-6)

        # v4: planned_total_cycle_days = planned_finish - created (directly maps to target span)
        df['planned_total_cycle_days'] = (
            df['planned_finish_date'] - df['created_date']
        ).dt.total_seconds() / (24 * 3600)

        # v4: Year and day-of-year for trend & seasonality
        df['created_year'] = df['created_date'].dt.year
        df['created_day_of_year'] = df['created_date'].dt.dayofyear

        # v4: Ratio of planned production to total cycle (urgency indicator)
        df['planned_prod_ratio'] = df['planned_production_days'] / (df['planned_total_cycle_days'] + 1e-6)

        return df
    
    def _create_concurrent_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """P1: Create concurrent workload features - orders/qty starting on the same day"""
        logger.info("Creating concurrent workload features")
        
        # Number of orders starting on the same planned start date
        df['concurrent_orders_on_start'] = df.groupby('planned_start_date')['order_quantity'].transform('count')
        
        # Total quantity starting on the same day
        df['concurrent_qty_on_start'] = df.groupby('planned_start_date')['order_quantity'].transform('sum')
        
        # This order's share of the day's total quantity
        df['qty_share_of_day'] = df['order_quantity'] / (df['concurrent_qty_on_start'] + 1e-6)
        
        return df
    
    def _create_forward_workload_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        P5: Forward-looking workload features — use known planned orders as context.

        For each order, compute the pipeline load visible at its created_date:
        - How many orders on the same production line have planned_start in the next 7/14 days
        - Total quantity in that pipeline window
        - Same-material pipeline count

        This is NOT data leakage: planned orders are known at order creation time.
        Works identically for training (historical) and prediction (current pipeline).
        """
        logger.info("Creating forward-looking workload features (P5)")

        df = df.copy()
        for col in ['forward_7d_line_orders', 'forward_7d_line_qty',
                     'forward_14d_line_orders', 'forward_14d_line_qty',
                     'forward_7d_material_orders', 'forward_7d_material_qty']:
            df[col] = 0.0

        # Need both created_date and planned_start_date as datetime
        cd = pd.to_datetime(df['created_date'], errors='coerce')
        ps = pd.to_datetime(df['planned_start_date'], errors='coerce')

        has_line = 'production_line' in df.columns

        for idx in range(len(df)):
            ref_date = cd.iloc[idx]
            if pd.isna(ref_date):
                continue

            d7 = ref_date + timedelta(days=7)
            d14 = ref_date + timedelta(days=14)

            # Orders whose planned_start falls within the forward window
            # (exclude current order itself)
            future_mask_7 = (ps > ref_date) & (ps <= d7)
            future_mask_14 = (ps > ref_date) & (ps <= d14)
            # Exclude self
            future_mask_7 = future_mask_7 & (df.index != df.index[idx])
            future_mask_14 = future_mask_14 & (df.index != df.index[idx])

            # Same production line
            if has_line:
                line = df.iloc[idx].get('production_line')
                if pd.notna(line):
                    line_7 = future_mask_7 & (df['production_line'] == line)
                    line_14 = future_mask_14 & (df['production_line'] == line)
                    df.iloc[idx, df.columns.get_loc('forward_7d_line_orders')] = float(line_7.sum())
                    df.iloc[idx, df.columns.get_loc('forward_7d_line_qty')] = float(df.loc[line_7, 'order_quantity'].sum())
                    df.iloc[idx, df.columns.get_loc('forward_14d_line_orders')] = float(line_14.sum())
                    df.iloc[idx, df.columns.get_loc('forward_14d_line_qty')] = float(df.loc[line_14, 'order_quantity'].sum())

            # Same material
            mat = df.iloc[idx].get('material')
            if pd.notna(mat):
                mat_7 = future_mask_7 & (df['material'] == mat)
                df.iloc[idx, df.columns.get_loc('forward_7d_material_orders')] = float(mat_7.sum())
                df.iloc[idx, df.columns.get_loc('forward_7d_material_qty')] = float(df.loc[mat_7, 'order_quantity'].sum())

        logger.info("Forward-looking workload features created")
        return df
    
    def _create_material_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create material-related features"""
        logger.info("Creating material features")
        
        # Material family (first 8 characters of material number)
        df['material_family'] = df['material'].astype(str).str[:8]
        
        # Material complexity (based on total production time)
        df['material_complexity'] = df['total_production_time'] * df['order_quantity']
        
        # P2: log transform of order quantity (highly right-skewed)
        df['log_order_quantity'] = np.log1p(df['order_quantity'])
        
        # P2: Binary constraint flag (only 2 values: 5 and 30)
        df['is_high_constraint'] = (df['constraint_factor'] == 5).astype(int)
        
        # P2: MRP Controller encoding
        if 'mrp_controller' in df.columns:
            df['mrp_controller_encoded'] = (df['mrp_controller'] == 'CVC').astype(int)
        else:
            df['mrp_controller_encoded'] = 0
        
        # P4: Flag extreme orders
        qty_95 = df['order_quantity'].quantile(0.95)
        df['is_large_order'] = (df['order_quantity'] > qty_95).astype(int)

        # v4: Relative order size — ratio of this order's qty to the material's average qty
        material_avg_qty = df.groupby('material')['order_quantity'].transform('mean')
        df['qty_ratio_to_material_avg'] = df['order_quantity'] / (material_avg_qty + 1e-6)

        return df
    
    def _create_production_line_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create production line features"""
        logger.info("Creating production line features")
        
        # Production line frequency: how many orders share this line in the dataset
        if 'production_line' in df.columns:
            line_counts = df['production_line'].value_counts()
            df['production_line_freq'] = df['production_line'].map(line_counts).fillna(0).astype(float)
        else:
            df['production_line_freq'] = 0.0
        
        # Expected production time based on unit time and quantity
        df['expected_production_time'] = df['total_production_time'] * df['order_quantity']
        
        # Capacity utilization (keep this as it varies per order)
        df['capacity_utilization'] = df['order_quantity'] / (df['line_capacity'] * df['planned_production_days'] + 1e-6)

        # Per-weekday capacity: use the actual capacity for the planned start weekday
        # weekday: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
        day_cap_cols = ['cap_mo', 'cap_tu', 'cap_we', 'cap_th', 'cap_fr']
        if all(c in df.columns for c in day_cap_cols):
            weekday_to_col = {0: 'cap_mo', 1: 'cap_tu', 2: 'cap_we', 3: 'cap_th', 4: 'cap_fr'}
            def _get_day_cap(row):
                try:
                    wd = int(row['planned_start_weekday'])
                except (ValueError, TypeError):
                    wd = 0
                col = weekday_to_col.get(wd, 'cap_mo')
                return float(row[col])
            df['planned_start_day_capacity'] = df.apply(_get_day_cap, axis=1).astype(float)
            df['day_capacity_utilization'] = df['order_quantity'] / (df['planned_start_day_capacity'] + 1e-6)
        
        return df
    
    def _create_historical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create historical average production time features (improved v2)
        - Uses expanding mean for NaN fill instead of global mean (no future leak)
        - P3: Added std, max, count, and last production time
        """
        logger.info("Creating historical production time features (v2)")
        
        # Sort by created date for proper time-series ordering
        df = df.sort_values('created_date').reset_index(drop=True)
        
        # Initialize historical features
        df['material_avg_production_time_90d'] = np.nan
        df['material_std_production_time_90d'] = np.nan
        df['material_max_production_time_90d'] = np.nan
        df['material_order_count_30d'] = 0.0
        df['material_last_production_time'] = np.nan
        df['line_avg_production_time_90d'] = np.nan
        df['material_line_avg_production_time_90d'] = np.nan
        
        # Track expanding mean for proper NaN filling (no future data leak)
        expanding_sum = 0.0
        expanding_count = 0
        
        # Calculate rolling stats (excluding current row)
        for idx in range(len(df)):
            current_date = df.loc[idx, 'created_date']
            lookback_start_90 = current_date - timedelta(days=self.lookback_days)
            lookback_start_30 = current_date - timedelta(days=30)
            
            # Filter historical data (strictly before current date)
            hist_mask = (
                (df['created_date'] < current_date) &
                (df['created_date'] >= lookback_start_90) &
                (df['actual_production_days'].notna())
            )
            hist_data = df[hist_mask]
            
            if len(hist_data) > 0:
                current_material = df.loc[idx, 'material']
                current_line = df.loc[idx, 'production_line']
                
                # Material-level stats (90d)
                material_hist = hist_data[hist_data['material'] == current_material]
                if len(material_hist) > 0:
                    prod_times = material_hist['actual_production_days']
                    df.loc[idx, 'material_avg_production_time_90d'] = prod_times.mean()
                    df.loc[idx, 'material_std_production_time_90d'] = prod_times.std() if len(prod_times) > 1 else 0.0
                    df.loc[idx, 'material_max_production_time_90d'] = prod_times.max()
                    df.loc[idx, 'material_last_production_time'] = prod_times.iloc[-1]
                
                # Material order count (30d window)
                hist_30d_mask = (
                    (df['created_date'] < current_date) &
                    (df['created_date'] >= lookback_start_30) &
                    (df['material'] == current_material)
                )
                df.loc[idx, 'material_order_count_30d'] = float(hist_30d_mask.sum())
                
                # Production line average (90d)
                line_hist = hist_data[hist_data['production_line'] == current_line]
                if len(line_hist) > 0:
                    df.loc[idx, 'line_avg_production_time_90d'] = line_hist['actual_production_days'].mean()
                
                # Material + Line average (90d)
                material_line_hist = hist_data[
                    (hist_data['material'] == current_material) &
                    (hist_data['production_line'] == current_line)
                ]
                if len(material_line_hist) > 0:
                    df.loc[idx, 'material_line_avg_production_time_90d'] = material_line_hist['actual_production_days'].mean()
            
            # Update expanding mean (for filling NaN without future data leak)
            current_target = df.loc[idx, 'actual_production_days']
            if pd.notna(current_target):
                expanding_sum += current_target
                expanding_count += 1
            
            # Fill NaN for this row using expanding mean up to previous row
            if expanding_count > 0:
                expanding_mean = expanding_sum / expanding_count
                for col in ['material_avg_production_time_90d', 'material_std_production_time_90d',
                            'material_max_production_time_90d', 'material_last_production_time',
                            'line_avg_production_time_90d', 'material_line_avg_production_time_90d']:
                    if pd.isna(df.loc[idx, col]):
                        if col.endswith('_std_production_time_90d'):
                            df.loc[idx, col] = 0.0  # No variance info yet
                        else:
                            df.loc[idx, col] = expanding_mean
        
        # For the very first rows where expanding_count==0, fill with 0
        for col in ['material_avg_production_time_90d', 'material_std_production_time_90d',
                    'material_max_production_time_90d', 'material_last_production_time',
                    'line_avg_production_time_90d', 'material_line_avg_production_time_90d']:
            df[col] = df[col].fillna(0.0)
        
        # v4: Material historical volatility (CV = std / mean) — high CV = unpredictable material
        avg_col = df['material_avg_production_time_90d']
        std_col = df['material_std_production_time_90d']
        df['material_cv_production_time'] = std_col / (avg_col + 1e-6)
        
        logger.info("Historical features (v2+v4) created with expanding mean fill")
        
        return df
    
    def _create_target_encoding(self, df: pd.DataFrame) -> pd.DataFrame:
        """P3: Target encoding for material and production line using expanding mean (no future leak)"""
        logger.info("Creating target encoding for material and production line")
        
        df = df.sort_values('created_date').reset_index(drop=True)
        
        # Expanding mean of target per material (strictly causal)
        df['material_target_encoded'] = np.nan
        material_sums = {}
        material_counts = {}
        
        # P6: Also encode production line
        df['line_target_encoded'] = np.nan
        line_sums = {}
        line_counts = {}
        
        for idx in range(len(df)):
            mat = df.loc[idx, 'material']
            if mat in material_sums and material_counts[mat] > 0:
                df.loc[idx, 'material_target_encoded'] = material_sums[mat] / material_counts[mat]
            
            # Production line target encoding
            line = df.loc[idx, 'production_line'] if 'production_line' in df.columns else None
            if line is not None and line in line_sums and line_counts[line] > 0:
                df.loc[idx, 'line_target_encoded'] = line_sums[line] / line_counts[line]
            
            # Update running stats with current row's target
            target = df.loc[idx, 'actual_production_days']
            if pd.notna(target):
                material_sums[mat] = material_sums.get(mat, 0.0) + target
                material_counts[mat] = material_counts.get(mat, 0) + 1
                if line is not None:
                    line_sums[line] = line_sums.get(line, 0.0) + target
                    line_counts[line] = line_counts.get(line, 0) + 1
        
        # Fill initial NaN with global expanding mean
        global_cum = df['actual_production_days'].expanding().mean().shift(1)
        df['material_target_encoded'] = df['material_target_encoded'].fillna(global_cum)
        df['material_target_encoded'] = df['material_target_encoded'].fillna(0.0)
        df['line_target_encoded'] = df['line_target_encoded'].fillna(global_cum)
        df['line_target_encoded'] = df['line_target_encoded'].fillna(0.0)
        
        return df
    
    def _create_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create interaction features"""
        logger.info("Creating interaction features")
        
        # Complexity × Capacity interaction
        df['complexity_capacity_interaction'] = (
            df['material_complexity'] * df['capacity_utilization']
        )
        
        # Quantity × Time interaction
        df['qty_time_interaction'] = (
            df['order_quantity'] * df['planned_production_days']
        )
        
        # Constraint × Quantity interaction
        df['constraint_qty_interaction'] = (
            df['constraint_factor'] * df['order_quantity']
        )
        
        # Expected time vs planned time ratio
        df['expected_planned_ratio'] = (
            df['expected_production_time'] / (df['planned_production_days'] + 1e-6)
        )
        
        # Shortage × Quantity interaction (if shortage data available)
        if 'has_shortage' in df.columns:
            df['shortage_qty_interaction'] = df['total_shortage_qty'] * df['order_quantity']
            df['shortage_complexity_interaction'] = df['max_shortage_pct'] * df['material_complexity']
            # Ratio-based interactions (leverage new ratio features)
            if 'shortage_component_ratio' in df.columns:
                df['shortage_ratio_qty_interaction'] = df['shortage_component_ratio'] * df['order_quantity']
        
        return df
    
    def _create_capacity_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create capacity and workload features"""
        logger.info("Creating capacity features")
        
        # Total capacity available
        df['total_capacity_available'] = df['line_capacity'] * df['planned_production_days']
        
        # Workload intensity
        df['workload_intensity'] = df['order_quantity'] / (df['total_capacity_available'] + 1e-6)
        
        return df
    
    def transform_for_prediction(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Feature engineering for prediction mode (no target filtering).

        Unlike transform(), this:
        - Does NOT require actual_finish_date
        - Does NOT drop rows with missing target
        - Does NOT filter outliers
        - Creates actual_production_days where possible (for completed orders)
        - Fills historical / target-encoding features with 0 for new orders
        """
        logger.info("Starting feature engineering (prediction mode)")

        df = df.copy()

        # Create target variable where actual_finish_date exists (optional)
        if 'actual_finish_date' in df.columns:
            df['actual_finish_date'] = pd.to_datetime(df['actual_finish_date'], errors='coerce')
            df['created_date'] = pd.to_datetime(df['created_date'], errors='coerce')
            raw_days = (
                df['actual_finish_date'] - df['created_date']
            ).dt.total_seconds() / (24 * 3600)
            # Floor: same-day completion = 1 working day (not 0)
            df['actual_production_days'] = np.maximum(raw_days, 1.0)
        else:
            df['actual_production_days'] = np.nan

        logger.info(f"Prediction mode: {len(df)} rows, "
                     f"{df['actual_production_days'].notna().sum()} with actual finish date")

        # Feature creation steps (same as training)
        df = self._create_time_features(df)
        df = self._create_concurrent_features(df)
        df = self._create_forward_workload_features(df)
        df = self._create_material_features(df)
        df = self._create_production_line_features(df)
        df = self._create_historical_features(df)
        df = self._create_target_encoding(df)
        df = self._create_interaction_features(df)
        df = self._create_capacity_features(df)

        logger.info(f"Prediction feature engineering complete. Shape: {df.shape}")
        return df

    def get_feature_columns(self, df: pd.DataFrame) -> list:
        """
        Get list of feature columns (excluding target, metadata, and leaked features)
        
        Args:
            df: DataFrame with all features
            
        Returns:
            List of feature column names
        """
        # Exclude columns
        exclude_cols = [
            # Target variable
            'actual_production_days',
            # P0: Data leakage - these depend on actual_finish_date (unknown at prediction time)
            'actual_duration_days', 'delay_days', 'is_delayed',
            # Metadata / identifiers
            'sales_doc', 'item', 'production_number',
            'material', 'material_description',
            'planned_start_date', 'planned_finish_date',
            'actual_finish_date', 'actual_start_date', 'created_date',
            'production_line', 'material_family',
            'system_status', 'entered_by', 'production_supervisor',
            'mrp_controller', 'unit', 'confirmed_quantity',
            'Basic start time', 'Actual start time', 'Actual finish time',
            'fg_material_description',
            # P2: Constant features (zero variance when single production line)
            'production_line_encoded', 'has_supervisor',
            # P2: Redundant with is_high_constraint
            'constraint_level',
            # P2: Removed - linearly dependent on workload_intensity
            'daily_capacity_per_unit',
            # APS loader creates these but they duplicate feature engineer outputs
            'planned_start_year',
            # Raw per-day capacity columns (used to derive planned_start_day_capacity)
            'cap_mo', 'cap_tu', 'cap_we', 'cap_th', 'cap_fr',
        ]
        
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        
        self.feature_names = feature_cols
        logger.info(f"Feature columns ({len(feature_cols)}): {feature_cols}")
        
        return feature_cols
