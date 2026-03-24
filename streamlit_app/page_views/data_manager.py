"""
页面1: 数据管理 (Dataset Manager)
"""
import streamlit as st
import pandas as pd
import io
from pathlib import Path
from loguru import logger
import sys
sys.path.append('.')

from src.config.paths import RAW_DATA_DIR, PROCESSED_DATA_DIR
from streamlit_app.ui import render_page_header, render_section_card


def _read_csv_with_encoding_fallback(source):
    """读取CSV时自动尝试常见编码，避免UTF-8解码失败。"""
    encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "utf-16", "utf-16le", "utf-16be", "cp1252", "latin1"]
    parse_errors = []
    last_error = None

    # 统一读取原始二进制，避免 UploadedFile 指针位置影响重试
    if isinstance(source, (str, Path)):
        raw_bytes = Path(source).read_bytes()
    elif hasattr(source, "getvalue"):
        raw_bytes = source.getvalue()
    elif hasattr(source, "read"):
        raw_bytes = source.read()
        if hasattr(source, "seek"):
            source.seek(0)
    else:
        raise TypeError("不支持的文件来源类型")

    # 某些情况下文件扩展名是 .csv，但内容是 Excel 文件
    if raw_bytes.startswith(b"PK"):
        try:
            df = pd.read_excel(io.BytesIO(raw_bytes))
            return df, "excel(binary)"
        except Exception:
            pass

    def _parse_csv_text(text: str):
        """对已解码文本做多策略解析，兼容分隔符不一致与坏行。"""
        strategies = [
            # 自动嗅探分隔符（逗号/分号/制表符等）
            {"sep": None, "engine": "python"},
            # 显式常见分隔符
            {"sep": ","},
            {"sep": ";"},
            {"sep": "\t"},
            {"sep": "|"},
            # 最后兜底：容错跳过坏行
            {"sep": None, "engine": "python", "on_bad_lines": "skip"},
            {"sep": ",", "engine": "python", "on_bad_lines": "skip"},
            {"sep": ";", "engine": "python", "on_bad_lines": "skip"},
            {"sep": "\t", "engine": "python", "on_bad_lines": "skip"},
            {"sep": "|", "engine": "python", "on_bad_lines": "skip"},
        ]

        parse_last_error = None
        for opts in strategies:
            try:
                df = pd.read_csv(io.StringIO(text), **opts)
                if df is not None and len(df.columns) > 0:
                    mode = (
                        f"robust({opts.get('sep')}, skip_bad={opts.get('on_bad_lines') == 'skip'})"
                    )
                    return df, mode
            except Exception as e:  # noqa: BLE001
                parse_last_error = e
                continue
        raise ValueError(f"CSV结构解析失败: {parse_last_error}")

    for enc in encodings:
        try:
            text = raw_bytes.decode(enc)
            df, parse_mode = _parse_csv_text(text)
            return df, f"{enc}, {parse_mode}"
        except Exception as e:  # noqa: BLE001 - fallback chain
            last_error = e
            parse_errors.append(f"{enc}: {e}")
            continue

    raise ValueError(
        "无法识别CSV编码或内容格式。"
        f" 已尝试编码: {', '.join(encodings)}。最后错误: {last_error}。"
        f" 详情: {' | '.join(parse_errors[:3])}"
    )


def _count_csv_rows_with_fallback(path: Path) -> int:
    """按编码回退统计CSV行数。"""
    encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "latin1"]
    for enc in encodings:
        try:
            with open(path, encoding=enc) as f:
                return max(sum(1 for _ in f) - 1, 0)
        except Exception:
            continue
    raise ValueError("无法读取CSV行数")


def show_data_manager():
    render_page_header("Data Manager", "上传、预览和验证 SAP 生产数据", "Data")

    tab_upload, tab_existing, tab_quality = st.tabs(["上传新数据", "使用现有数据", "数据质量"])

    # ── Tab 1: 上传新数据 ──
    with tab_upload:
        with render_section_card("Upload SAP Files", "支持 CSV / Excel，拖拽或点击上传"):
            st.caption("Upload Engine v3: 自动编码识别（UTF-8 / GB18030 / GBK / Latin1）")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**必需文件**")
                history_file = st.file_uploader("History.csv (历史生产订单)", type=["csv", "xlsx"], key="hist")
                fg_file = st.file_uploader("FG.csv (成品物料主数据)", type=["csv", "xlsx"], key="fg")
                capacity_file = st.file_uploader("Capacity.csv (产线产能)", type=["csv", "xlsx"], key="cap")

            with col2:
                st.markdown("**可选文件 (MRP数据)**")
                mrp_file = st.file_uploader("mrp_results.csv (MRP运行结果)", type=["csv", "xlsx"], key="mrp")
                po_file = st.file_uploader("purchase_orders.csv (采购订单)", type=["csv", "xlsx"], key="po")
                stock_file = st.file_uploader("stock_levels.csv (库存数据)", type=["csv", "xlsx"], key="stock")
                bom_file = st.file_uploader("bom_data.csv (BOM数据)", type=["csv", "xlsx"], key="bom")

        if st.button("加载上传数据", type="primary", key="load_uploaded"):
            uploaded = {
                'History.csv': history_file,
                'FG.csv': fg_file,
                'Capacity.csv': capacity_file,
                'mrp_results.csv': mrp_file,
                'purchase_orders.csv': po_file,
                'stock_levels.csv': stock_file,
                'bom_data.csv': bom_file,
            }

            loaded_count = 0
            raw_dfs = {}
            data_dir = RAW_DATA_DIR
            data_dir.mkdir(parents=True, exist_ok=True)

            for name, file in uploaded.items():
                if file is not None:
                    try:
                        if file.name.endswith('.xlsx'):
                            df = pd.read_excel(file)
                            used_encoding = "excel"
                        else:
                            df, used_encoding = _read_csv_with_encoding_fallback(file)
                        # 保存到 data/raw/
                        save_path = data_dir / name
                        df.to_csv(save_path, index=False, encoding='utf-8-sig')
                        raw_dfs[name] = df
                        loaded_count += 1
                        st.success(f"{name}: {len(df)} 行 x {len(df.columns)} 列")
                        if used_encoding not in {"excel", "utf-8", "utf-8-sig"}:
                            st.caption(f"{name} 已按 {used_encoding} 编码读取并转换为 UTF-8 存储")
                    except Exception as e:
                        st.error(f"[Upload Engine v3] {name} 加载失败: {e}")

            if loaded_count > 0:
                st.session_state['raw_dataframes'] = raw_dfs
                st.session_state['data_source'] = 'upload'
                st.success(f"已加载 {loaded_count} 个文件")

    # ── Tab 2: 使用现有数据 ──
    with tab_existing:
        with render_section_card("Raw Data Folder", "从 data/raw 扫描并合并已有数据"):
            data_dir = RAW_DATA_DIR

            if data_dir.exists():
                csv_files = list(data_dir.glob("*.csv"))
                if csv_files:
                    file_info = []
                    for f in sorted(csv_files):
                        if f.name.startswith('.'):
                            continue
                        try:
                            row_count = _count_csv_rows_with_fallback(f)
                        except Exception:
                            row_count = "?"
                        file_info.append({
                            '文件名': f.name,
                            '大小': f"{f.stat().st_size / 1024:.1f} KB",
                            '行数': row_count,
                        })

                    st.dataframe(pd.DataFrame(file_info), width='stretch', hide_index=True)

                    if st.button("加载并合并现有数据", type="primary", key="load_existing"):
                        _load_and_merge_existing()
                else:
                    st.warning(f"{data_dir} 目录中没有CSV文件")
            else:
                st.warning(f"{data_dir} 目录不存在")

        with render_section_card("Processed Dataset", "直接载入已处理的数据快照"):
            processed_dir = PROCESSED_DATA_DIR
            if processed_dir.exists():
                processed_files = list(processed_dir.glob("*.csv"))
                if processed_files:
                    selected = st.selectbox(
                        "选择已处理数据文件",
                        [f.name for f in processed_files]
                    )
                    if st.button("加载已处理数据", key="load_processed"):
                        try:
                            df, _ = _read_csv_with_encoding_fallback(processed_dir / selected)
                            if 'planned_start_date' in df.columns:
                                df['planned_start_date'] = pd.to_datetime(df['planned_start_date'])
                            if 'planned_finish_date' in df.columns:
                                df['planned_finish_date'] = pd.to_datetime(df['planned_finish_date'])
                            if 'actual_finish_date' in df.columns:
                                df['actual_finish_date'] = pd.to_datetime(df['actual_finish_date'])

                            st.session_state['merged_df'] = df
                            st.session_state['data_loaded'] = True
                            st.session_state['data_source'] = 'processed'
                            st.success(f"加载完成: {len(df)} 行 x {len(df.columns)} 列")
                        except Exception as e:
                            st.error(f"加载失败: {e}")

    # ── Tab 3: 数据质量 ──
    with tab_quality:
        _show_data_quality_tab()

    # ── 数据预览 ──
    if st.session_state.get('merged_df') is not None:
        with render_section_card("Merged Dataset Preview", "合并后的关键统计与样本预览"):
            df = st.session_state['merged_df']

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("总行数", f"{len(df):,}")
            with col2:
                st.metric("总列数", f"{len(df.columns)}")
            with col3:
                if 'is_delayed' in df.columns:
                    delay_rate = df['is_delayed'].mean()
                    st.metric("延迟率", f"{delay_rate:.1%}")
                else:
                    st.metric("延迟率", "N/A")
            with col4:
                missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
                st.metric("缺失率", f"{missing_pct:.1f}%")

            st.dataframe(df.head(100), width='stretch', height=400)


def _load_and_merge_existing():
    """加载现有数据文件并合并"""
    try:
        from src.data_processing.aps_data_loader import APSDataLoader

        with st.spinner("正在加载和合并数据..."):
            loader = APSDataLoader(data_dir=str(RAW_DATA_DIR))
            df = loader.load_and_merge()

            is_valid, errors = loader.validate_data(df)
            if not is_valid:
                for err in errors:
                    st.warning(f"验证警告: {err}")

            st.session_state['merged_df'] = df
            st.session_state['data_loaded'] = True
            st.session_state['data_source'] = 'existing'

            # 同时保存各原始表引用
            raw_dfs = {}
            if loader.history_df is not None:
                raw_dfs['History.csv'] = loader.history_df
            if loader.fg_df is not None:
                raw_dfs['FG.csv'] = loader.fg_df
            if loader.capacity_df is not None:
                raw_dfs['Capacity.csv'] = loader.capacity_df
            st.session_state['raw_dataframes'] = raw_dfs

            # 加载MRP数据(如果存在)
            from src.data_collection.csv_loader import CSVLoader
            csv_loader = CSVLoader(data_dir=str(RAW_DATA_DIR))
            mrp_dfs = {}
            for name, method in [
                ('mrp_results.csv', csv_loader.load_mrp_results),
                ('purchase_orders.csv', csv_loader.load_purchase_orders),
                ('bom_data.csv', csv_loader.load_bom_data),
                ('stock_levels.csv', csv_loader.load_stock_levels),
            ]:
                result = method()
                if result is not None:
                    mrp_dfs[name] = result
            if mrp_dfs:
                st.session_state['mrp_dataframes'] = mrp_dfs
                st.info(f"发现并加载了 {len(mrp_dfs)} 个MRP数据文件")

            st.success(f"数据加载完成: {len(df)} 行 x {len(df.columns)} 列")
            st.rerun()

    except Exception as e:
        st.error(f"数据加载失败: {e}")
        logger.error(f"Data loading error: {e}")


def _show_data_quality_tab():
    """数据质量检查tab"""
    if st.session_state.get('merged_df') is None:
        st.info("请先在 '上传新数据' 或 '使用现有数据' 中加载数据")
        return

    df = st.session_state['merged_df']

    from streamlit_app.components.data_quality import (
        run_quality_check, render_quality_report, render_missing_heatmap
    )
    from src.data_processing.data_quality import DataQualityChecker

    with render_section_card("Data Quality Check", "运行通用质量检查与生产专项校验"):
        if st.button("运行数据质量检查", type="primary", key="run_quality"):
            with st.spinner("检查中..."):
                report = run_quality_check(df, "合并数据集")
                render_quality_report(report)

                st.subheader("缺失值分布")
                render_missing_heatmap(df)

                checker = DataQualityChecker()
                is_valid, issues = checker.validate_production_data(df)
                if issues:
                    st.subheader("生产数据专项检查")
                    for issue in issues:
                        st.warning(issue)
                else:
                    st.success("生产数据专项检查通过")

                st.subheader("列级统计")
                col_stats = []
                for col in df.columns:
                    stat = {
                        '列名': col,
                        '类型': str(df[col].dtype),
                        '缺失数': df[col].isnull().sum(),
                        '缺失率': f"{df[col].isnull().sum() / len(df) * 100:.1f}%",
                        '唯一值': df[col].nunique(),
                    }
                    col_stats.append(stat)
                st.dataframe(pd.DataFrame(col_stats), width='stretch', height=400, hide_index=True)
