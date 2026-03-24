"""
MRP特征工程模块
"""
import pandas as pd
import numpy as np
from loguru import logger


class MRPFeatureEngineer:
    """MRP相关特征工程"""

    def __init__(self, lookback_days: int = 90):
        self.lookback_days = lookback_days

    def transform(self, orders_df: pd.DataFrame,
                   mrp_df: pd.DataFrame = None,
                   po_df: pd.DataFrame = None,
                   bom_df: pd.DataFrame = None,
                   stock_df: pd.DataFrame = None) -> pd.DataFrame:
        """
        生成MRP相关特征

        Args:
            orders_df: 生产订单DataFrame (已含基础特征)
            mrp_df: MRP运行结果 (可选)
            po_df: 采购订单 (可选)
            bom_df: BOM数据 (可选)
            stock_df: 库存数据 (可选)

        Returns:
            添加了MRP特征的DataFrame
        """
        df = orders_df.copy()

        if mrp_df is not None:
            df = self._create_shortage_features(df, mrp_df)
            logger.info(f"MRP供需特征已生成")

        if po_df is not None:
            df = self._create_supplier_features(df, po_df)
            logger.info(f"采购交付特征已生成")

        if bom_df is not None:
            df = self._create_bom_features(df, bom_df)
            logger.info(f"BOM特征已生成")

        if stock_df is not None:
            df = self._create_stock_features(df, stock_df)
            logger.info(f"库存特征已生成")

        if any(x is not None for x in [mrp_df, po_df, bom_df, stock_df]):
            df = self._create_mrp_interaction_features(df)
            logger.info(f"MRP交互特征已生成")

        return df

    def _create_shortage_features(self, df: pd.DataFrame, mrp_df: pd.DataFrame) -> pd.DataFrame:
        """MRP供需缺口特征"""
        mrp = mrp_df.copy()

        # 标准化列名
        col_map = {
            'Material': 'material', 'Material Number': 'material',
            'Shortage Qty': 'shortage_qty', 'Shortage': 'shortage_qty',
            'Demand Qty': 'demand_qty', 'Supply Qty': 'supply_qty',
            'Exception': 'exception_type',
        }
        mrp = mrp.rename(columns={k: v for k, v in col_map.items() if k in mrp.columns})

        if 'shortage_qty' in mrp.columns:
            shortage_agg = mrp.groupby('material').agg(
                total_shortage=('shortage_qty', 'sum'),
                shortage_count=('shortage_qty', lambda x: (x > 0).sum()),
            ).reset_index()

            df = df.merge(shortage_agg, on='material', how='left')
            df['material_shortage_flag'] = (df['total_shortage'] > 0).astype(int)
            df['total_shortage'] = df['total_shortage'].fillna(0)
            df['shortage_count'] = df['shortage_count'].fillna(0)
        else:
            df['material_shortage_flag'] = 0
            df['total_shortage'] = 0
            df['shortage_count'] = 0

        if 'demand_qty' in mrp.columns and 'supply_qty' in mrp.columns:
            ds_agg = mrp.groupby('material').agg(
                total_demand=('demand_qty', 'sum'),
                total_supply=('supply_qty', 'sum'),
            ).reset_index()
            ds_agg['demand_supply_ratio'] = ds_agg['total_demand'] / ds_agg['total_supply'].clip(lower=1)
            df = df.merge(ds_agg[['material', 'demand_supply_ratio']], on='material', how='left')
            df['demand_supply_ratio'] = df['demand_supply_ratio'].fillna(1.0)
        else:
            df['demand_supply_ratio'] = 1.0

        if 'exception_type' in mrp.columns:
            exc_count = mrp.groupby('material')['exception_type'].count().reset_index()
            exc_count.columns = ['material', 'mrp_exception_count']
            df = df.merge(exc_count, on='material', how='left')
            df['mrp_exception_count'] = df['mrp_exception_count'].fillna(0)
        else:
            df['mrp_exception_count'] = 0

        return df

    def _create_supplier_features(self, df: pd.DataFrame, po_df: pd.DataFrame) -> pd.DataFrame:
        """采购交付特征"""
        po = po_df.copy()

        col_map = {
            'Material': 'material', 'Material Number': 'material',
            'Delivery Date': 'delivery_date', 'Actual Delivery': 'actual_delivery',
            'Vendor': 'vendor', 'Supplier': 'vendor',
            'Status': 'po_status',
            'Delay Days': 'po_delay_days',
        }
        po = po.rename(columns={k: v for k, v in col_map.items() if k in po.columns})

        if 'po_delay_days' in po.columns:
            po_agg = po.groupby('material').agg(
                avg_po_delay=('po_delay_days', 'mean'),
                po_ontime_rate=('po_delay_days', lambda x: (x <= 0).mean()),
            ).reset_index()
            df = df.merge(po_agg, on='material', how='left')
            df['avg_po_delay'] = df['avg_po_delay'].fillna(0)
            df['supplier_ontime_rate'] = df['po_ontime_rate'].fillna(1.0)
            df.drop(columns=['po_ontime_rate'], inplace=True, errors='ignore')
        else:
            df['avg_po_delay'] = 0
            df['supplier_ontime_rate'] = 1.0

        if 'po_status' in po.columns:
            open_po = po[po['po_status'].str.lower().isin(['open', 'pending', 'partial'])]
            open_count = open_po.groupby('material').size().reset_index(name='open_po_count')
            df = df.merge(open_count, on='material', how='left')
            df['open_po_count'] = df['open_po_count'].fillna(0)
        else:
            df['open_po_count'] = 0

        return df

    def _create_bom_features(self, df: pd.DataFrame, bom_df: pd.DataFrame) -> pd.DataFrame:
        """BOM复杂度特征"""
        bom = bom_df.copy()

        col_map = {
            'Material': 'material', 'Parent Material': 'material',
            'Component': 'component', 'Component Material': 'component',
            'Level': 'bom_level', 'BOM Level': 'bom_level',
            'Qty': 'component_qty', 'Quantity': 'component_qty',
        }
        bom = bom.rename(columns={k: v for k, v in col_map.items() if k in bom.columns})

        if 'material' in bom.columns:
            bom_agg = bom.groupby('material').agg(
                bom_component_count=('component', 'nunique') if 'component' in bom.columns else ('material', 'count'),
                bom_depth=('bom_level', 'max') if 'bom_level' in bom.columns else ('material', 'count'),
            ).reset_index()
            df = df.merge(bom_agg, on='material', how='left')
            df['bom_component_count'] = df['bom_component_count'].fillna(0)
            df['bom_depth'] = df['bom_depth'].fillna(0)
        else:
            df['bom_component_count'] = 0
            df['bom_depth'] = 0

        return df

    def _create_stock_features(self, df: pd.DataFrame, stock_df: pd.DataFrame) -> pd.DataFrame:
        """库存特征"""
        stock = stock_df.copy()

        col_map = {
            'Material': 'material', 'Material Number': 'material',
            'Unrestricted': 'unrestricted_stock',
            'Quality Inspection': 'quality_stock',
            'Blocked': 'blocked_stock',
            'Safety Stock': 'safety_stock',
        }
        stock = stock.rename(columns={k: v for k, v in col_map.items() if k in stock.columns})

        if 'unrestricted_stock' in stock.columns:
            stock_agg = stock.groupby('material').agg(
                total_stock=('unrestricted_stock', 'sum'),
            ).reset_index()

            if 'quality_stock' in stock.columns:
                quality_agg = stock.groupby('material')['quality_stock'].sum().reset_index()
                stock_agg = stock_agg.merge(quality_agg, on='material', how='left')
                stock_agg['quality_hold_ratio'] = (
                    stock_agg['quality_stock'] /
                    (stock_agg['total_stock'] + stock_agg['quality_stock']).clip(lower=1)
                )
            else:
                stock_agg['quality_hold_ratio'] = 0.0

            if 'safety_stock' in stock.columns:
                safety_agg = stock.groupby('material')['safety_stock'].sum().reset_index()
                stock_agg = stock_agg.merge(safety_agg, on='material', how='left')
                stock_agg['safety_stock_ratio'] = (
                    stock_agg['total_stock'] / stock_agg['safety_stock'].clip(lower=1)
                )
            else:
                stock_agg['safety_stock_ratio'] = 1.0

            df = df.merge(
                stock_agg[['material', 'total_stock', 'quality_hold_ratio', 'safety_stock_ratio']],
                on='material', how='left'
            )
            df['total_stock'] = df['total_stock'].fillna(0)
            df['quality_hold_ratio'] = df['quality_hold_ratio'].fillna(0)
            df['safety_stock_ratio'] = df['safety_stock_ratio'].fillna(1.0)
        else:
            df['total_stock'] = 0
            df['quality_hold_ratio'] = 0
            df['safety_stock_ratio'] = 1.0

        return df

    def _create_mrp_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """MRP交互特征"""
        if 'material_shortage_flag' in df.columns and 'material_delay_rate_90d' in df.columns:
            df['shortage_delay_interaction'] = (
                df['material_shortage_flag'] * df['material_delay_rate_90d']
            )

        if 'demand_supply_ratio' in df.columns and 'qty_capacity_ratio' in df.columns:
            df['supply_capacity_pressure'] = df['demand_supply_ratio'] * df['qty_capacity_ratio']

        return df

    def get_mrp_feature_names(self) -> list:
        """返回所有可能的MRP特征名"""
        return [
            # 供需类
            'material_shortage_flag',
            'total_shortage',
            'shortage_count',
            'demand_supply_ratio',
            'mrp_exception_count',
            # 采购类
            'avg_po_delay',
            'supplier_ontime_rate',
            'open_po_count',
            # BOM类
            'bom_component_count',
            'bom_depth',
            # 库存类
            'total_stock',
            'quality_hold_ratio',
            'safety_stock_ratio',
            # 交互类
            'shortage_delay_interaction',
            'supply_capacity_pressure',
        ]
