"""
OpenSQL Response Transformer
将 SAP OpenSQL 返回的 JSON 行转换为与现有 CSV 列名一致的 DataFrame
"""
import re
import pandas as pd
from typing import List, Dict, Any
from loguru import logger


class OpenSQLTransformer:
    """将 SAP 原始 JSON 转换为与 aps_data_loader 兼容的 CSV 格式"""

    # ==================================================================
    # FG.csv
    # ==================================================================
    @staticmethod
    def transform_fg(rows: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        SAP → FG.csv 列名

        alias → CSV:
            PRODUCTION_LINE   → Production Line
            MATERIAL          → Material  (去前导零)
            MATERIAL_DESCRIPTION → Material Description
            CONSTRAINT_FACTOR → Constraint
            EARLIEST_START    → earlist strart date  (保留原CSV拼写)
            TOTAL_PRODUCTION_TIME → Total production Time
            TPT_FACTOR        → TPT Factor  (新列)
        """
        if not rows:
            logger.warning("FG 查询返回 0 行")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        rename = {
            "PRODUCTION_LINE": "Production Line",
            "MATERIAL": "Material",
            "MATERIAL_DESCRIPTION": "Material Description",
            "CONSTRAINT_FACTOR": "Constraint",
            "EARLIEST_START": "earlist strart date",
            "TOTAL_PRODUCTION_TIME": "Total production Time",
            "TPT_FACTOR": "TPT Factor",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

        df["Material"] = df["Material"].apply(_strip_leading_zeros)
        _to_numeric(df, ["Constraint", "earlist strart date", "Total production Time", "TPT Factor"])

        logger.info(f"FG: {len(df)} 行, {df['Production Line'].nunique()} 产线")
        return df

    # ==================================================================
    # Capacity.csv
    # ==================================================================
    @staticmethod
    def transform_capacity(rows: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        SAP → Capacity.csv 列名

        alias → CSV:
            PRODUCTION_LINE → Production Line
            CAPACITY_MO/TU/WE/TH/FR → Capacity Mo/Tu/We/Th/Fr
        """
        if not rows:
            logger.warning("Capacity 查询返回 0 行")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        rename = {
            "PRODUCTION_LINE": "Production Line",
            "CAPACITY_MO": "Capacity Mo",
            "CAPACITY_TU": "Capacity Tu",
            "CAPACITY_WE": "Capacity We",
            "CAPACITY_TH": "Capacity Th",
            "CAPACITY_FR": "Capacity Fr",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

        cap_cols = [c for c in df.columns if c.startswith("Capacity")]
        _to_numeric(df, cap_cols)

        logger.info(f"Capacity: {len(df)} 行")
        return df

    # ==================================================================
    # History.csv
    # ==================================================================
    @staticmethod
    def transform_history(rows: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        SAP → History.csv 列名

        alias → CSV  (须与 aps_data_loader.preprocess_history column_mapping 匹配):
            SALES_ORDER        → Sales Order
            SALES_ORDER_ITEM   → Sales Order Item
            ORDER_NUMBER       → Order  (去前导零)
            MATERIAL_NUMBER    → Material Number  (去前导零)
            MATERIAL_DESCRIPTION → Material description
            ORDER_QUANTITY     → Order quantity (GMEIN)
            BASIC_FINISH_DATE  → Basic finish date  (YYYYMMDD→YYYY-MM-DD)
            BASIC_START_DATE   → Basic start date
            ACTUAL_START_DATE  → Actual start time  (YYYYMMDD→YYYY-MM-DD)
            ACTUAL_FINISH_DATE → Actual finish date
            CREATED_ON         → Created on
            MRP_CONTROLLER     → MRP controller
            PRODN_SUPERVISOR   → Prodn Supervisor
        """
        if not rows:
            logger.warning("History 查询返回 0 行")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        rename = {
            "SALES_ORDER": "Sales Order",
            "SALES_ORDER_ITEM": "Sales Order Item",
            "ORDER_NUMBER": "Order",
            "MATERIAL_NUMBER": "Material Number",
            "MATERIAL_DESCRIPTION": "Material description",
            "ORDER_QUANTITY": "Order quantity (GMEIN)",
            "BASIC_FINISH_DATE": "Basic finish date",
            "BASIC_START_DATE": "Basic start date",
            "ACTUAL_START_DATE": "Actual start time",
            "ACTUAL_FINISH_DATE": "Actual finish date",
            "CREATED_ON": "Created on",
            "MRP_CONTROLLER": "MRP controller",
            "PRODN_SUPERVISOR": "Prodn Supervisor",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

        # 去前导零
        df["Order"] = df["Order"].apply(_strip_leading_zeros)
        df["Material Number"] = df["Material Number"].apply(_strip_leading_zeros)

        # DATS → YYYY-MM-DD
        date_cols = [
            "Basic start date",
            "Basic finish date",
            "Actual start time",
            "Actual finish date",
            "Created on",
        ]
        for col in date_cols:
            if col in df.columns:
                df[col] = df[col].apply(_convert_sap_date)

        _to_numeric(df, ["Order quantity (GMEIN)"])

        logger.info(f"History: {len(df)} 行, {df['Material Number'].nunique()} 物料")
        return df

    # ==================================================================
    # Shortage.csv
    # ==================================================================
    @staticmethod
    def transform_shortage(rows: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        SAP → Shortage.csv 列名

        alias → CSV:
            ORDER_NUMBER   → Order  (去前导零)
            MATERIAL       → Material  (去前导零)
            REQMNT_QTY     → Reqmnt qty
            QTY_WITHDRAWN  → Available qty  (已领 = 可用)
            REQMTS_DATE    → ReqmtsDate  (YYYYMMDD→M/D/YYYY)
            (计算)          → Shortage qty = Reqmnt qty - Available qty
        """
        if not rows:
            logger.warning("Shortage 查询返回 0 行")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        rename = {
            "ORDER_NUMBER": "Order",
            "MATERIAL": "Material",
            "REQMNT_QTY": "Reqmnt qty",
            "QTY_WITHDRAWN": "Available qty",
            "REQMTS_DATE": "ReqmtsDate",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

        # 去前导零
        df["Order"] = df["Order"].apply(_strip_leading_zeros)
        df["Material"] = df["Material"].apply(_strip_leading_zeros)

        # 数值类型
        _to_numeric(df, ["Reqmnt qty", "Available qty"])

        # 计算缺料量
        df["Shortage qty"] = df["Reqmnt qty"] - df["Available qty"]

        # 日期格式 → 与现有 CSV 一致 (M/D/YYYY)
        if "ReqmtsDate" in df.columns:
            df["ReqmtsDate"] = df["ReqmtsDate"].apply(_convert_sap_date_short)

        logger.info(f"Shortage: {len(df)} 行, {df['Order'].nunique()} 订单")
        return df


# ======================================================================
# 辅助函数
# ======================================================================

def _strip_leading_zeros(val: Any) -> str:
    """去除 SAP 前导零: '000000CDX6090704R5001' → 'CDX6090704R5001'"""
    if pd.isna(val):
        return ""
    s = str(val).strip()
    return s.lstrip("0") or "0"


def _convert_sap_date(val: Any) -> str:
    """
    DATS(YYYYMMDD) → YYYY-MM-DD

    已是 YYYY-MM-DD 格式则原样返回；空值/00000000 返回空串
    """
    if pd.isna(val):
        return ""
    s = str(val).strip()
    if not s or s == "00000000":
        return ""
    # 已是 YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    # YYYYMMDD
    if re.match(r"^\d{8}$", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def _convert_sap_date_short(val: Any) -> str:
    """
    DATS(YYYYMMDD) → M/D/YYYY（与现有 Shortage.csv 格式匹配）
    """
    if pd.isna(val):
        return ""
    s = str(val).strip()
    if not s or s == "00000000":
        return ""
    if re.match(r"^\d{8}$", s):
        month = int(s[4:6])
        day = int(s[6:])
        year = s[:4]
        return f"{month}/{day}/{year}"
    return s


def _to_numeric(df: pd.DataFrame, cols: List[str]):
    """将指定列转为数值型"""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
