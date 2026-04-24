"""
OpenSQL Query Builder
为 4 类数据集（FG / Capacity / History / Shortage）生成 ABAP OpenSQL 查询语句
"""
from typing import List, Optional
from loguru import logger


# SAP IN clause 安全上限（避免过长 SQL）
_MAX_IN_VALUES = 500


class OpenSQLBuilder:
    """构建 ABAP OpenSQL 查询语句"""

    def __init__(self, plant: str = "1202"):
        self.plant = plant

    # ==================================================================
    # FG（成品物料主数据）
    # ==================================================================
    def build_fg_query(self) -> str:
        """
        ZPP_PRODLINE_MAT → FG.csv

        返回字段:
            PRODUCTION_LINE, MATERIAL, MATERIAL_DESCRIPTION,
            CONSTRAINT_FACTOR, EARLIEST_START, TOTAL_PRODUCTION_TIME, TPT_FACTOR
        """
        sql = (
            "SELECT"
            "  PRODLINE  AS PRODUCTION_LINE,"
            "  MATNR     AS MATERIAL,"
            "  MAKTX     AS MATERIAL_DESCRIPTION,"
            "  PJCN      AS CONSTRAINT_FACTOR,"
            "  ZZQD      AS EARLIEST_START,"
            "  TPT       AS TOTAL_PRODUCTION_TIME,"
            "  ZSXS      AS TPT_FACTOR"
            "  FROM ZPP_PRODLINE_MAT"
            "  INTO TABLE @DATA(lt_data)."
        )
        return sql

    # ==================================================================
    # Capacity（产能）
    # ==================================================================
    def build_capacity_query(self) -> str:
        """
        ZPP_CAPACITY → Capacity.csv

        过滤条件: PLANT + 当前有效期
        返回字段:
            PRODUCTION_LINE, CAPACITY_MO … CAPACITY_FR
        """
        sql = (
            "SELECT"
            "  FEVOR     AS PRODUCTION_LINE,"
            "  CAP_MON   AS CAPACITY_MO,"
            "  CAP_TUE   AS CAPACITY_TU,"
            "  CAP_WED   AS CAPACITY_WE,"
            "  CAP_THU   AS CAPACITY_TH,"
            "  CAP_FRI   AS CAPACITY_FR"
            f"  FROM ZPP_CAPACITY"
            f"  WHERE PLANT = '{self.plant}'"
            "  AND VALID_FROM <= @( sy-datum )"
            "  AND VALID_TO   >= @( sy-datum )"
            "  INTO TABLE @DATA(lt_data)."
        )
        return sql

    # ==================================================================
    # History（生产订单历史）
    # ==================================================================
    def build_history_queries(
        self,
        material_list: List[str],
        date_from: str,
        date_to: Optional[str] = None,
    ) -> List[str]:
        """
        CAUFV + MAKT → History.csv

        Args:
            material_list: FG 中取到的物料号（SAP 原始格式，含前导零）
            date_from: YYYYMMDD 格式
            date_to:   YYYYMMDD 格式（默认 sy-datum）

        Returns:
            查询列表（当物料数量超限时自动分批）
        """
        if not material_list:
            logger.warning("material_list 为空，跳过 History 查询")
            return []

        date_filter = f"AND caufv~ERDAT >= '{date_from}'"
        if date_to:
            date_filter += f" AND caufv~ERDAT <= '{date_to}'"
        else:
            date_filter += " AND caufv~ERDAT <= @( sy-datum )"

        batches = _chunk(material_list, _MAX_IN_VALUES)
        queries: List[str] = []

        for batch in batches:
            in_clause = _build_in_list(batch)
            sql = (
                "SELECT"
                "  caufv~KDAUF  AS SALES_ORDER,"
                "  caufv~KDPOS  AS SALES_ORDER_ITEM,"
                "  caufv~AUFNR  AS ORDER_NUMBER,"
                "  caufv~PLNBEZ AS MATERIAL_NUMBER,"
                "  makt~MAKTX   AS MATERIAL_DESCRIPTION,"
                "  caufv~GAMNG  AS ORDER_QUANTITY,"
                "  caufv~GLTRP  AS BASIC_FINISH_DATE,"
                "  caufv~GSTRP  AS BASIC_START_DATE,"
                "  caufv~GSTRI  AS ACTUAL_START_DATE,"
                "  caufv~GLTRI  AS ACTUAL_FINISH_DATE,"
                "  caufv~ERDAT  AS CREATED_ON,"
                "  caufv~DISPO  AS MRP_CONTROLLER,"
                "  caufv~FEVOR  AS PRODN_SUPERVISOR"
                "  FROM caufv"
                "  INNER JOIN makt ON makt~matnr = caufv~plnbez AND makt~spras = 'E'"
                f"  WHERE caufv~PLNBEZ IN ({in_clause})"
                f"  {date_filter}"
                "  INTO TABLE @DATA(lt_data)."
            )
            queries.append(sql)

        logger.info(f"History: {len(material_list)} 物料 → {len(queries)} 批查询")
        return queries

    # ==================================================================
    # Shortage（缺料）
    # ==================================================================
    def build_shortage_queries(self, order_list: List[str]) -> List[str]:
        """
        RESB → Shortage.csv

        Args:
            order_list: History 中取到的订单号（SAP 原始格式，含前导零）

        Returns:
            查询列表（自动分批）
        """
        if not order_list:
            logger.warning("order_list 为空，跳过 Shortage 查询")
            return []

        batches = _chunk(order_list, _MAX_IN_VALUES)
        queries: List[str] = []

        for batch in batches:
            in_clause = _build_in_list(batch)
            sql = (
                "SELECT"
                "  resb~AUFNR  AS ORDER_NUMBER,"
                "  resb~MATNR  AS MATERIAL,"
                "  resb~BDMNG  AS REQMNT_QTY,"
                "  resb~ENMNG  AS QTY_WITHDRAWN,"
                "  resb~BDTER  AS REQMTS_DATE"
                "  FROM resb"
                f"  WHERE resb~AUFNR IN ({in_clause})"
                f"  AND resb~WERKS = '{self.plant}'"
                "  INTO TABLE @DATA(lt_data)."
            )
            queries.append(sql)

        logger.info(f"Shortage: {len(order_list)} 订单 → {len(queries)} 批查询")
        return queries


# ======================================================================
# 辅助函数
# ======================================================================

def _build_in_list(values: List[str]) -> str:
    """构建 IN ('val1', 'val2', ...) 内部字符串"""
    escaped = [v.replace("'", "''") for v in values]
    return ", ".join(f"'{v}'" for v in escaped)


def _chunk(lst: List[str], size: int) -> List[List[str]]:
    """将列表按 size 切分"""
    return [lst[i : i + size] for i in range(0, len(lst), size)]
