"""
SAP Data Fetch Orchestrator
按 DAG 依赖顺序获取 FG → [Capacity, History] → Shortage，并保存为 CSV
"""
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

from .opensql_client import SAPOpenSQLClient
from .opensql_queries import OpenSQLBuilder
from .opensql_transformer import OpenSQLTransformer


class SAPDataFetcher:
    """
    编排 4 步数据获取 DAG:

        Step 1:  FG  (主数据)
        Step 2a: Capacity   ┐ 并行
        Step 2b: History    ┘
        Step 3:  Shortage   (依赖 History 的订单列表)

    注意：跨表 IN 查询使用 SAP 原始字段值（含前导零），
          CSV 输出则经 transformer 去零处理。
    """

    def __init__(
        self,
        client: SAPOpenSQLClient,
        plant: str = "1202",
        output_dir: str = "data/raw",
    ):
        self.client = client
        self.builder = OpenSQLBuilder(plant=plant)
        self.transformer = OpenSQLTransformer()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ==================================================================
    # 主入口
    # ==================================================================
    def fetch_all(
        self,
        date_from: str,
        date_to: Optional[str] = None,
        save_csv: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """
        执行完整 DAG，返回 4 个 DataFrame

        Args:
            date_from: History 增量起始日期 (YYYYMMDD)
            date_to:   History 截止日期 (YYYYMMDD)，默认 sy-datum（今天）
            save_csv:  是否写入 data/raw/*.csv

        Returns:
            {"fg": df, "capacity": df, "history": df, "shortage": df}
        """
        logger.info("=" * 60)
        logger.info("SAP OpenSQL — 开始数据抽取")
        logger.info(f"  日期范围: {date_from} ~ {date_to or 'today'}")
        logger.info("=" * 60)

        # ---- Step 1: FG ----
        logger.info("\n[Step 1/4] 获取 FG（成品物料主数据）")
        fg_raw_rows = self._execute_fg()
        fg_df = self.transformer.transform_fg(fg_raw_rows)
        if fg_df.empty:
            raise RuntimeError("FG 查询返回 0 行，终止后续步骤")

        # 使用 SAP 原始 MATNR（含前导零）作为 History IN 条件
        material_list_raw = _extract_raw_field(fg_raw_rows, "MATERIAL")
        logger.info(f"  → 物料列表: {len(material_list_raw)} 个")

        # ---- Step 2: Capacity + History（可并行） ----
        logger.info("\n[Step 2/4] 并行获取 Capacity + History")
        with ThreadPoolExecutor(max_workers=2) as pool:
            future_cap = pool.submit(self._fetch_capacity)
            future_hist = pool.submit(
                self._fetch_history_raw, material_list_raw, date_from, date_to
            )
            capacity_df = future_cap.result()
            hist_raw_rows = future_hist.result()

        history_df = self.transformer.transform_history(hist_raw_rows)

        # ---- Step 3: Shortage（依赖 History） ----
        logger.info("\n[Step 3/4] 获取 Shortage（缺料数据）")
        # 使用 SAP 原始 AUFNR（含前导零）作为 Shortage IN 条件
        order_list_raw = _extract_raw_field(hist_raw_rows, "ORDER_NUMBER")
        logger.info(f"  → 订单列表: {len(order_list_raw)} 个")
        shortage_df = self._fetch_shortage(order_list_raw)

        # ---- 保存 ----
        result = {
            "fg": fg_df,
            "capacity": capacity_df,
            "history": history_df,
            "shortage": shortage_df,
        }

        if save_csv:
            self._save_all(result)

        self._print_summary(result)
        return result

    # ==================================================================
    # 各步骤
    # ==================================================================
    def _execute_fg(self) -> List[Dict[str, Any]]:
        sql = self.builder.build_fg_query()
        return self.client.execute(sql)

    def _fetch_capacity(self) -> pd.DataFrame:
        sql = self.builder.build_capacity_query()
        rows = self.client.execute(sql)
        return self.transformer.transform_capacity(rows)

    def _fetch_history_raw(
        self,
        material_list: List[str],
        date_from: str,
        date_to: Optional[str],
    ) -> List[Dict[str, Any]]:
        """执行 History 查询，返回原始 JSON 行（不做 transform）"""
        queries = self.builder.build_history_queries(material_list, date_from, date_to)
        all_rows: List[Dict[str, Any]] = []
        for i, sql in enumerate(queries, 1):
            logger.info(f"  History 批次 {i}/{len(queries)}")
            rows = self.client.execute(sql)
            all_rows.extend(rows)
        return all_rows

    def _fetch_shortage(self, order_list: List[str]) -> pd.DataFrame:
        if not order_list:
            logger.warning("History 返回 0 订单，跳过 Shortage")
            return pd.DataFrame()

        queries = self.builder.build_shortage_queries(order_list)
        all_rows: List[Dict[str, Any]] = []
        for i, sql in enumerate(queries, 1):
            logger.info(f"  Shortage 批次 {i}/{len(queries)}")
            rows = self.client.execute(sql)
            all_rows.extend(rows)
        return self.transformer.transform_shortage(all_rows)

    # ==================================================================
    # 保存 & 汇总
    # ==================================================================
    def _save_all(self, result: Dict[str, pd.DataFrame]):
        """保存 4 个 CSV，若文件被占用则自动加时间戳保存"""
        file_map = {
            "fg": "FG.csv",
            "capacity": "Capacity.csv",
            "history": "History.csv",
            "shortage": "Shortage.csv",
        }
        for key, filename in file_map.items():
            df = result[key]
            if df.empty:
                logger.warning(f"  {filename} 为空，跳过保存")
                continue
            path = self.output_dir / filename
            try:
                df.to_csv(path, index=False, encoding="utf-8")
            except PermissionError:
                # 文件被占用（如 Excel 打开），用带时间戳的备用名保存
                from datetime import datetime as _dt
                stem = path.stem
                alt = self.output_dir / f"{stem}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.csv"
                logger.warning(f"  {filename} 被占用，改存为 {alt.name}")
                df.to_csv(alt, index=False, encoding="utf-8")
                path = alt
            logger.info(f"  ✓ 保存 {path.name}: {len(df)} 行")

    @staticmethod
    def _print_summary(result: Dict[str, pd.DataFrame]):
        logger.info("\n" + "=" * 60)
        logger.info("数据抽取完成")
        for key, df in result.items():
            logger.info(f"  {key:>10}: {len(df):>8,} 行")
        logger.info("=" * 60)


# ======================================================================
# 辅助
# ======================================================================

def _extract_raw_field(rows: List[Dict[str, Any]], field: str) -> List[str]:
    """从原始 JSON 行中提取某字段的唯一值列表（保留 SAP 原始格式）"""
    seen = set()
    result: List[str] = []
    for r in rows:
        v = str(r.get(field, "")).strip()
        if v and v not in seen:
            seen.add(v)
            result.append(v)
    return result
