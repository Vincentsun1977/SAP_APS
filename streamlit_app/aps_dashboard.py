"""
APS TPT (Total Production Time) Prediction Dashboard
基于APS数据的生产时长预测系统
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os
import numpy as np
from pathlib import Path as _Path

# 预测文件目录（真实目录）
_PRED_DIR = _Path(__file__).parent.parent / "predictions"

sys.path.append('.')

# 加载 .env 文件中的环境变量
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=False)

# Page config
st.set_page_config(
    page_title="APS TPT 生产时长预测",
    page_icon="⏱️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.markdown('<h1 class="main-header">⏱️ APS TPT 生产时长预测</h1>', unsafe_allow_html=True)
    st.markdown("---")

    st.sidebar.title("🎛️ 控制面板")
    st.sidebar.markdown("### 导航菜单")

    page = st.sidebar.radio(
        "导航菜单",
        ["📥 数据管理", "🤖 模型训练与测试", "🔮 TPT预测", "📁 预测结果"],
        label_visibility="collapsed",
    )

    if page == "📥 数据管理":
        show_data_management()
    elif page == "🤖 模型训练与测试":
        show_model_training()
    elif page == "🔮 TPT预测":
        show_tpt_prediction()
    elif page == "📁 预测结果":
        show_predictions()


# ======================================================================
# 页面 1: 数据管理
# ======================================================================

def show_data_management():
    st.header("📥 数据管理")
    st.markdown("从 SAP ECC 通过 OpenSQL API 抽取 FG / Capacity / History / Shortage 数据到本地 CSV")
    st.markdown("---")

    # ---- 连接配置 ----
    st.subheader("🔌 连接配置")
    col1, col2 = st.columns(2)
    with col1:
        endpoint = st.text_input(
            "API 端点",
            value=os.environ.get(
                "SAP_OPENSQL_ENDPOINT",
                "https://test.nas-saperp.abb.com/abb/ybc_query_mind//SAPQueryMind"
            ),
            help="SAP OpenSQL API 的完整 URL",
        )
        sap_client = st.text_input(
            "SAP Client",
            value=os.environ.get("SAP_OPENSQL_CLIENT", "800")
        )
        plant = st.text_input(
            "工厂代码 (Plant)",
            value=os.environ.get("SAP_OPENSQL_PLANT", "1202")
        )
    with col2:
        # 从环境变量读取 token 作为默认值
        env_token = os.environ.get("SAP_OPENSQL_TOKEN", "")
        auth_token = st.text_input(
            "Authorization Token (Basic)",
            value=env_token,
            type="password",
            help="已编码的 Base64 认证令牌。保存后会写入 .env 文件，刷新页面自动加载。",
        )
        output_dir = st.text_input("输出目录", value="data/raw")

        # 保存所有连接配置到 .env
        if st.button("💾 保存连接配置到 .env", use_container_width=True):
            token_val = auth_token.strip()
            if token_val:
                _save_connection_config(
                    token=token_val,
                    endpoint=endpoint.strip(),
                    sap_client=sap_client.strip(),
                    plant=plant.strip(),
                )
                st.success("✅ 连接配置已保存到 .env，刷新页面后自动加载。")
            else:
                st.warning("Token 为空，未保存。")

    # ---- 日期范围 ----
    st.subheader("📅 数据范围")
    col1, col2, col3 = st.columns(3)
    with col1:
        sync_mode = st.radio("同步模式", ["增量（最近N天）", "自定义日期范围"], horizontal=True)
    with col2:
        if sync_mode == "增量（最近N天）":
            days_back = st.number_input("回溯天数", min_value=1, max_value=730, value=30, step=1)
            date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
            date_to = None
            st.info(f"将获取 {date_from[:4]}-{date_from[4:6]}-{date_from[6:]} 至今的数据")
        else:
            d_from = st.date_input("起始日期", value=datetime(2024, 1, 1))
            date_from = d_from.strftime("%Y%m%d")
            date_to = None
    with col3:
        if sync_mode != "增量（最近N天）":
            use_end_date = st.checkbox("指定截止日期（默认=今天）")
            if use_end_date:
                d_to = st.date_input("截止日期", value=datetime.now())
                date_to = d_to.strftime("%Y%m%d")

    st.markdown("---")

    # ---- 按钮区 ----
    col_test, col_fetch = st.columns(2)

    with col_test:
        test_clicked = st.button("🧪 测试连接", use_container_width=True)
    with col_fetch:
        fetch_clicked = st.button("🚀 开始抽取数据", type="primary", use_container_width=True)

    # ---- 构建 client config ----
    def _build_config():
        token = auth_token.strip()
        if not token:
            st.error("请输入 Authorization Token")
            return None
        return {
            "endpoint": endpoint.strip(),
            "sap_client": sap_client.strip(),
            "auth": {"type": "basic_token", "token": token},
            "request": {"timeout": 120, "max_retries": 3, "retry_delay": 5, "verify_ssl": False},
            "plant": plant.strip(),
        }

    # ---- 测试连接 ----
    if test_clicked:
        cfg = _build_config()
        if cfg is None:
            return
        token = cfg["auth"]["token"]
        st.caption(f"🔑 Token 长度: {len(token)}，前4位: `{token[:4]}`, 末4位: `{token[-4:]}`")
        with st.spinner("正在测试 SAP OpenSQL API 连接..."):
            try:
                import importlib, src.sap_integration.opensql_client as _mod
                importlib.reload(_mod)
                client = _mod.SAPOpenSQLClient(cfg)
                auth_header = client.session.headers.get("Authorization", "")
                st.caption(f"📡 Auth Header: `{auth_header[:20]}...{auth_header[-8:]}`")
                client.test_connection()
                st.success("✅ 连接成功！API 可正常响应。")
            except Exception as e:
                st.error(f"❌ 连接失败: {type(e).__name__}: {e}")

    # ---- 数据抽取 ----
    if fetch_clicked:
        cfg = _build_config()
        if cfg is None:
            return

        from src.sap_integration.opensql_client import SAPOpenSQLClient
        from src.sap_integration.opensql_fetcher import SAPDataFetcher

        client = SAPOpenSQLClient(cfg)
        fetcher = SAPDataFetcher(client=client, plant=plant, output_dir=output_dir)

        progress = st.progress(0, text="初始化...")
        log_area = st.empty()
        logs: list[str] = []

        def _log(msg: str):
            logs.append(f"`{datetime.now().strftime('%H:%M:%S')}` {msg}")
            log_area.markdown("\n\n".join(logs[-15:]))  # 显示最近 15 条

        try:
            # Step 1: FG
            progress.progress(5, text="[1/4] 获取 FG（成品物料主数据）...")
            _log("📦 正在获取 FG 主数据...")
            fg_raw = fetcher._execute_fg()
            fg_df = fetcher.transformer.transform_fg(fg_raw)
            _log(f"✅ FG: {len(fg_df)} 行, {fg_df['Production Line'].nunique() if not fg_df.empty else 0} 产线")
            if fg_df.empty:
                st.error("FG 查询返回 0 行，终止。")
                return
            progress.progress(20, text="FG 完成")

            from src.sap_integration.opensql_fetcher import _extract_raw_field
            material_list_raw = _extract_raw_field(fg_raw, "MATERIAL")
            _log(f"📋 物料列表: {len(material_list_raw)} 个")

            # Step 2: Capacity + History
            progress.progress(25, text="[2/4] 获取 Capacity...")
            _log("⚙️ 正在获取 Capacity 产能数据...")
            capacity_df = fetcher._fetch_capacity()
            _log(f"✅ Capacity: {len(capacity_df)} 行")
            progress.progress(40, text="Capacity 完成")

            progress.progress(45, text="[3/4] 获取 History（生产订单历史）...")
            _log(f"📜 正在获取 History（日期 {date_from} ~ {date_to or '今天'}）...")
            hist_raw = fetcher._fetch_history_raw(material_list_raw, date_from, date_to)
            history_df = fetcher.transformer.transform_history(hist_raw)
            _log(f"✅ History: {len(history_df)} 行, {history_df['Material Number'].nunique() if not history_df.empty else 0} 物料")
            progress.progress(65, text="History 完成")

            # Step 3: Shortage
            order_list_raw = _extract_raw_field(hist_raw, "ORDER_NUMBER")
            _log(f"📋 订单列表: {len(order_list_raw)} 个")
            progress.progress(70, text="[4/4] 获取 Shortage（缺料数据）...")
            _log("🔧 正在获取 Shortage 缺料数据...")
            shortage_df = fetcher._fetch_shortage(order_list_raw)
            _log(f"✅ Shortage: {len(shortage_df)} 行, {shortage_df['Order'].nunique() if not shortage_df.empty else 0} 订单")
            progress.progress(90, text="Shortage 完成")

            # 保存
            result = {"fg": fg_df, "capacity": capacity_df, "history": history_df, "shortage": shortage_df}
            try:
                fetcher._save_all(result)
                _log("💾 CSV 文件已保存到 " + output_dir)
            except PermissionError as pe:
                _log(f"⚠️ 部分文件被占用: {pe}（请关闭 Excel 后重试）")
                st.warning(f"部分文件被占用无法覆盖，已用带时间戳的文件名保存。请关闭 Excel 中打开的 CSV 文件后重试。")
            progress.progress(100, text="✅ 全部完成！")

            # ---- 结果汇总 ----
            st.markdown("---")
            st.subheader("📊 抽取结果")
            summary_cols = st.columns(4)
            file_names = ["FG.csv", "Capacity.csv", "History.csv", "Shortage.csv"]
            dfs = [fg_df, capacity_df, history_df, shortage_df]
            icons = ["📦", "⚙️", "📜", "🔧"]
            for i, (col, name, df, icon) in enumerate(zip(summary_cols, file_names, dfs, icons)):
                with col:
                    st.metric(f"{icon} {name}", f"{len(df):,} 行")

            # 数据预览
            st.subheader("🔍 数据预览")
            preview_tab = st.tabs(file_names)
            for tab, name, df in zip(preview_tab, file_names, dfs):
                with tab:
                    if df.empty:
                        st.info(f"{name} 无数据")
                    else:
                        st.dataframe(df.head(20), use_container_width=True)

        except Exception as e:
            progress.progress(0, text="❌ 失败")
            _log(f"❌ 异常: {e}")
            st.error(f"数据抽取失败: {e}")

    # ====================================================================
    # 当前数据状态（始终显示，从磁盘读取）
    # ====================================================================
    st.markdown("---")
    _show_data_on_disk(output_dir)


# ======================================================================
# 页面 2: 模型训练与测试
# ======================================================================

def show_model_training():
    st.header("🤖 模型训练与测试")
    st.markdown("使用 `data/raw` 中的 CSV 数据训练 XGBoost 生产时长回归模型")

    output_dir = "data/raw"

    # 当前数据状态
    _show_data_on_disk(output_dir)

    # 最近一次训练结果
    _show_latest_training_on_disk()

    # ====================================================================
    # 模型训练
    # ====================================================================

    # 检查数据是否就绪
    raw_dir = _Path(output_dir)
    required_files = ["History.csv", "FG.csv", "Capacity.csv"]
    missing = [f for f in required_files if not (raw_dir / f).exists()]
    if missing:
        st.warning(f"缺少必要数据文件: {', '.join(missing)}。请先完成 SAP 数据抽取。")
    else:
        st.success(f"✅ 数据就绪 ({', '.join(required_files)} + Shortage.csv)")

    # ---- 超参数配置 ----
    with st.expander("⚙️ 训练超参数", expanded=True):
        hp_col1, hp_col2, hp_col3 = st.columns(3)
        with hp_col1:
            hp_test_size = st.slider("测试集比例", 0.10, 0.40, 0.20, 0.05,
                                     help="时序分割：前 N% 训练，后 (1-N)% 测试")
            hp_max_depth = st.number_input("max_depth", 3, 12, 6, 1)
            hp_n_estimators = st.number_input("n_estimators", 50, 1000, 500, 50)
            hp_learning_rate = st.number_input("learning_rate", 0.01, 0.30, 0.03, 0.01, format="%.2f")
        with hp_col2:
            hp_subsample = st.number_input("subsample", 0.5, 1.0, 0.8, 0.05, format="%.2f")
            hp_colsample = st.number_input("colsample_bytree", 0.5, 1.0, 0.8, 0.05, format="%.2f")
            hp_gamma = st.number_input("gamma", 0.0, 1.0, 0.1, 0.05, format="%.2f")
            hp_min_child = st.number_input("min_child_weight", 1, 10, 2, 1)
        with hp_col3:
            hp_reg_alpha = st.number_input("reg_alpha (L1)", 0.0, 2.0, 0.1, 0.1, format="%.1f")
            hp_reg_lambda = st.number_input("reg_lambda (L2)", 0.0, 3.0, 1.5, 0.1, format="%.1f")
            hp_early_stop = st.number_input("early_stopping_rounds", 5, 50, 30, 5)
            hp_cv_folds = st.number_input("CV 折数 (TimeSeriesCV)", 3, 10, 5, 1)

        st.markdown("---")
        hp_max_wait_days = st.slider(
            "最大等待天数过滤", 0, 15, 3, 1,
            help="排除等待时间(创建日→实际开工日)≥ N 天的历史工单。设为 0 则不过滤。")

        # P2: Optuna
        st.markdown("**🔍 Optuna 超参数自动搜索**")
        hp_use_optuna = st.checkbox(
            "启用 Optuna 自动调参（训练前先运行超参搜索，建议在数据较少时使用）",
            value=False,
            help="开启后，系统会先运行 N 次试验寻找最优超参，再训练最终模型，耗时较长。"
        )
        hp_optuna_trials = 50
        if hp_use_optuna:
            hp_optuna_trials = st.number_input("Optuna 试验次数", 10, 200, 50, 10,
                                               help="次数越多结果越好但耗时越长")

        # 汇总展示
        st.markdown(
            f"**当前配置**: test_size=**{hp_test_size}** · "
            f"max_depth=**{hp_max_depth}** · n_estimators=**{hp_n_estimators}** · "
            f"lr=**{hp_learning_rate}** · subsample=**{hp_subsample}** · "
            f"early_stop=**{hp_early_stop}** · CV=**{hp_cv_folds}**-fold · "
            f"损失=**Huber** · Optuna=**{'ON' if hp_use_optuna else 'OFF'}**"
        )

    train_clicked = st.button("🚀 开始训练模型", type="primary", use_container_width=True, disabled=bool(missing))

    if train_clicked:
        model_params = {
            "objective": "reg:pseudohubererror",
            "huber_slope": 1.0,
            "eval_metric": ["rmse", "mae"],
            "max_depth": hp_max_depth,
            "min_child_weight": hp_min_child,
            "subsample": hp_subsample,
            "colsample_bytree": hp_colsample,
            "gamma": hp_gamma,
            "reg_alpha": hp_reg_alpha,
            "reg_lambda": hp_reg_lambda,
            "learning_rate": hp_learning_rate,
            "n_estimators": hp_n_estimators,
            "random_state": 42,
            "n_jobs": -1,
            "early_stopping_rounds": hp_early_stop,
        }
        _run_training(output_dir, model_params, hp_test_size, hp_cv_folds, hp_max_wait_days,
                      use_optuna=hp_use_optuna, optuna_trials=hp_optuna_trials)

    # ====================================================================
    # 模型测试（独立于训练的评估）
    # ====================================================================
    st.markdown("---")
    st.header("🧪 模型测试")
    st.markdown("加载已训练模型，支持**调整测试集划分**或**上传新数据**进行独立评估")

    model_latest = _Path("models") / "production_time_model_latest.json"
    if not model_latest.exists() or missing:
        st.info("请先完成模型训练，生成 `production_time_model_latest.json`。")
    else:
        test_mode = st.radio(
            "测试模式", ["📊 调整测试集比例", "📂 上传新数据预测"],
            horizontal=True, key="test_mode",
        )

        if test_mode == "📊 调整测试集比例":
            st.caption(
                "训练时使用的是 **时序尾部 N%** 作为测试集。\n"
                "这里可以调整比例来观察不同划分下的模型表现差异。\n"
                "**提示**: 设置与训练不同的比例（如 30%、40%）才能看到差异化的结果。"
            )
            test_size_for_eval = st.slider(
                "测试集比例", 0.10, 0.50, 0.30, 0.05,
                key="eval_test_size",
                help="从数据尾部取该比例样本作为测试集。与训练时比例不同时，测试集范围会变化。",
            )
            # 筛选条件
            with st.expander("🔍 筛选条件（可选）", expanded=False):
                filter_col1, filter_col2 = st.columns(2)
                with filter_col1:
                    filter_material = st.text_input(
                        "物料号筛选（逗号分隔，留空=全部）",
                        value="", key="filter_mat",
                        help="只评估特定物料的预测效果",
                    )
                with filter_col2:
                    filter_max_days = st.number_input(
                        "仅评估实际天数 ≤ N 的订单", 5, 30, 30, 1,
                        key="filter_days",
                    )
            if st.button("▶️ 运行模型测试", use_container_width=True):
                mat_list = [m.strip() for m in filter_material.split(",") if m.strip()] if filter_material.strip() else None
                _run_model_test(output_dir, str(model_latest), test_size_for_eval, mat_list, filter_max_days)

        else:  # 上传新数据
            st.caption(
                "上传包含订单信息的 CSV 文件进行预测。\n"
                "如果 CSV 中包含 **actual_finish_date** 或 **Actual finish date** 列，将自动计算并对比预测误差。"
            )
            uploaded = st.file_uploader("上传 CSV（需包含与 History.csv 相同格式的列）", type=["csv"])
            if uploaded is not None:
                if st.button("▶️ 预测上传数据", use_container_width=True):
                    _run_model_predict_uploaded(uploaded, str(model_latest), output_dir)


# ======================================================================
# 页面 3: TPT 预测
# ======================================================================

def show_tpt_prediction():
    st.header("🔮 TPT 物料生产时长预测")
    st.markdown("基于历史工单训练模型 → 逐工单预测 → **按物料聚合**输出每个物料的预测 TPT（天）")

    output_dir = "data/raw"
    model_latest = _Path("models") / "production_time_model_latest.json"

    if not model_latest.exists():
        st.warning("请先在 **🤖 模型训练与测试** 页面训练模型。")
        return

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📌 模型信息")
    mtime = datetime.fromtimestamp(model_latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    st.sidebar.info(f"**模型文件**: `{model_latest.name}`\n\n**更新时间**: {mtime}")

    # ---- 聚合方式 ----
    st.sidebar.markdown("### ⚙️ 聚合设置")
    agg_method = st.sidebar.radio(
        "物料 TPT 聚合方式",
        ["中位数 (median)", "均值 (mean)"],
        index=0, key="tpt_agg_method",
        help="同一物料多个工单的预测值，用哪种方式汇总为该物料的 TPT",
    )

    st.markdown("---")

    # ---- 数据来源 ----
    data_source = st.radio(
        "数据来源",
        ["📂 上传 CSV 文件", "📜 使用本地 History.csv", "🔗 从 SAP 实时获取"],
        horizontal=True, key="tpt_source",
    )

    if data_source == "📂 上传 CSV 文件":
        st.caption("上传格式同 History.csv 的 CSV 文件。无需 actual_finish_date 列。")
        uploaded = st.file_uploader("上传生产订单 CSV", type=["csv"], key="tpt_upload")
        if uploaded is not None:
            if st.button("🔮 运行 TPT 预测", type="primary", use_container_width=True):
                _run_tpt_prediction(uploaded_file=uploaded, model_path=str(model_latest),
                                    data_dir=output_dir, agg_method=agg_method)

    elif data_source == "📜 使用本地 History.csv":
        history_path = _Path(output_dir) / "History.csv"
        if not history_path.exists():
            st.warning("History.csv 不存在，请先在 **📥 数据管理** 页面抽取数据。")
        else:
            nrows = sum(1 for _ in open(history_path, encoding="utf-8")) - 1
            st.info(f"将对本地 `History.csv` 中的 **{nrows:,}** 条订单进行预测")
            if st.button("🔮 运行 TPT 预测", type="primary", use_container_width=True):
                _run_tpt_prediction(uploaded_file=None, model_path=str(model_latest),
                                    data_dir=output_dir, agg_method=agg_method)

    else:  # 从 SAP 实时获取
        st.caption("从 SAP 实时拉取生产订单并预测。需要在 **📥 数据管理** 页面配置过 Token。")
        col_sap1, col_sap2 = st.columns(2)
        with col_sap1:
            sap_days = st.number_input("回溯天数", 1, 730, 30, 1, key="tpt_sap_days",
                                       help="获取最近 N 天创建的生产订单")
        with col_sap2:
            sap_plant = st.text_input("工厂代码", value="1202", key="tpt_sap_plant")

        env_token = os.environ.get("SAP_OPENSQL_TOKEN", "")
        if not env_token:
            st.warning("未检测到 SAP Token，请先在 **📥 数据管理** 页面保存 Token。")
        else:
            st.success(f"🔑 已检测到 Token（长度 {len(env_token)}）")
            if st.button("🔮 从 SAP 获取并预测", type="primary", use_container_width=True):
                _fetch_sap_and_predict(
                    model_path=str(model_latest),
                    data_dir=output_dir,
                    token=env_token,
                    plant=sap_plant,
                    days_back=sap_days,
                    agg_method=agg_method,
                )

    # ---- 最近一次预测结果 ----
    _show_latest_tpt_predictions()


def _fetch_sap_and_predict(model_path: str, data_dir: str, token: str,
                           plant: str, days_back: int, agg_method: str = "中位数 (median)"):
    """从 SAP 实时获取生产订单，然后执行 TPT 预测"""
    import importlib
    import src.sap_integration.opensql_client as _cli_mod
    import src.sap_integration.opensql_fetcher as _fet_mod
    importlib.reload(_cli_mod); importlib.reload(_fet_mod)
    from src.sap_integration.opensql_client import SAPOpenSQLClient
    from src.sap_integration.opensql_fetcher import SAPDataFetcher, _extract_raw_field

    # 每次执行前重新加载 .env，确保保存后的最新配置生效
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)

    progress = st.progress(0, text="连接 SAP...")
    logs: list[str] = []
    log_area = st.empty()

    def _log(msg: str):
        logs.append(f"`{datetime.now().strftime('%H:%M:%S')}` {msg}")
        log_area.markdown("\n\n".join(logs[-10:]))

    try:
        cfg = {
            "endpoint": os.environ.get("SAP_OPENSQL_ENDPOINT", "").strip(),
            "sap_client": os.environ.get("SAP_OPENSQL_CLIENT", "800").strip(),
            "auth": {"type": "basic_token", "token": token},
            "request": {"timeout": 120, "max_retries": 3, "retry_delay": 5, "verify_ssl": False},
            "plant": plant,
        }
        client = SAPOpenSQLClient(cfg)
        fetcher = SAPDataFetcher(client=client, plant=plant, output_dir=data_dir)

        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")

        # 1. FG
        _log("📦 获取 FG 主数据...")
        fg_raw = fetcher._execute_fg()
        fg_df = fetcher.transformer.transform_fg(fg_raw)
        if fg_df.empty:
            st.error("FG 查询返回 0 行，请检查连接。")
            return
        material_list_raw = _extract_raw_field(fg_raw, "MATERIAL")
        _log(f"✅ FG: {len(fg_df)} 行, {len(material_list_raw)} 物料")
        progress.progress(20, text="FG 完成")

        # 2. Capacity
        _log("⚙️ 获取 Capacity...")
        capacity_df = fetcher._fetch_capacity()
        _log(f"✅ Capacity: {len(capacity_df)} 行")
        progress.progress(35, text="Capacity 完成")

        # 3. History
        _log(f"📜 获取 History（{date_from} ~ 今天）...")
        hist_raw = fetcher._fetch_history_raw(material_list_raw, date_from, None)
        history_df = fetcher.transformer.transform_history(hist_raw)
        _log(f"✅ History: {len(history_df)} 行")
        progress.progress(55, text="History 完成")

        if history_df.empty:
            progress.progress(0)
            st.warning("History 查询返回 0 行，请调整回溯天数。")
            return

        # 4. Shortage
        order_list_raw = _extract_raw_field(hist_raw, "ORDER_NUMBER")
        _log(f"🔧 获取 Shortage（{len(order_list_raw)} 订单）...")
        shortage_df = fetcher._fetch_shortage(order_list_raw)
        _log(f"✅ Shortage: {len(shortage_df)} 行")
        progress.progress(70, text="Shortage 完成")

        _log("🔮 数据获取完成，开始 TPT 预测...")

        # 将 SAP 拿到的 history_df 作为 uploaded CSV 传入预测流程
        import io
        csv_buf = io.StringIO()
        history_df.to_csv(csv_buf, index=False)
        csv_buf.seek(0)

        progress.progress(75, text="开始预测...")

        # 直接调用预测核心函数
        _run_tpt_prediction(uploaded_file=csv_buf, model_path=model_path, data_dir=data_dir,
                            agg_method=agg_method)

    except Exception as e:
        progress.progress(0, text="❌ 失败")
        _log(f"❌ {e}")
        st.error(f"SAP 数据获取失败: {e}")
        import traceback
        st.code(traceback.format_exc(), language="text")


def _run_tpt_prediction(uploaded_file, model_path: str, data_dir: str,
                        agg_method: str = "中位数 (median)"):
    """对生产订单执行 TPT 预测，按物料聚合输出"""
    import importlib
    import src.data_processing.aps_data_loader as _ld_mod
    import src.data_processing.production_time_feature_engineer as _fe_mod
    import src.models.production_time_model as _md_mod
    importlib.reload(_ld_mod); importlib.reload(_fe_mod); importlib.reload(_md_mod)
    from src.data_processing.aps_data_loader import APSDataLoader
    from src.data_processing.production_time_feature_engineer import ProductionTimeFeatureEngineer
    from src.models.production_time_model import ProductionTimeModel

    progress = st.progress(0, text="加载数据...")
    try:
        loader = APSDataLoader(data_dir=data_dir)
        loader.load_all_files()
        if uploaded_file is not None:
            loader.history_df = pd.read_csv(uploaded_file, encoding="utf-8")
        progress.progress(15, text="文件加载完成")

        # 预测模式：保留所有订单（含未完成），只做列重命名和日期转换
        history_raw = loader.history_df.copy()
        # 复用 preprocess_history 的列重命名和日期转换，但不过滤已完成订单
        col_map = {
            'Sales Order': 'sales_doc', 'Sales Order Item': 'item',
            'Order': 'production_number', 'Material Number': 'material',
            'Material description': 'material_description',
            'System Status': 'system_status',
            'Order quantity (GMEIN)': 'order_quantity',
            'Confirmed quantity (GMEIN)': 'confirmed_quantity',
            'Basic start date': 'planned_start_date',
            'Basic finish date': 'planned_finish_date',
            'Actual finish date': 'actual_finish_date',
            'Actual start time': 'actual_start_date',
            'Unit of measure (=GMEIN)': 'unit',
            'Created on': 'created_date', 'Entered by': 'entered_by',
            'Prodn Supervisor': 'production_supervisor',
            'MRP controller': 'mrp_controller',
        }
        history_raw = history_raw.rename(columns=col_map)
        for c in ['planned_start_date', 'planned_finish_date', 'actual_finish_date',
                   'actual_start_date', 'created_date']:
            if c in history_raw.columns:
                history_raw[c] = pd.to_datetime(history_raw[c], errors='coerce')
        # 计算 planned_duration_days 和 delay 相关列（某些特征依赖）
        history_raw['planned_duration_days'] = (
            history_raw['planned_finish_date'] - history_raw['planned_start_date']
        ).dt.days
        history_raw['delay_days'] = 0
        history_raw['is_delayed'] = 0

        n_total = len(history_raw)
        n_completed = history_raw['actual_finish_date'].notna().sum()
        st.caption(f"📊 加载 {n_total} 条订单（{n_completed} 已完成, {n_total - n_completed} 在制/未完成）")

        df = loader.merge_with_fg_data(history_raw)
        df = loader.merge_with_capacity(df)
        df = loader.merge_with_shortage(df)
        df = loader._create_basic_features(df)
        progress.progress(30, text="数据合并完成")

        fe = ProductionTimeFeatureEngineer(lookback_days=90)
        df_featured = fe.transform_for_prediction(df)
        feature_cols = fe.get_feature_columns(df_featured)
        X = df_featured[feature_cols].fillna(0).copy()
        progress.progress(50, text=f"特征工程完成 — {len(X)} 条订单, {len(feature_cols)} 特征")

        model = ProductionTimeModel()
        model.load(model_path)
        y_pred = model.predict(X)
        progress.progress(80, text="预测完成")

        # ---- 工单级结果 ----
        order_result = df_featured[['material']].copy().reset_index(drop=True)
        if 'material_description' in df_featured.columns:
            order_result['material_description'] = df_featured['material_description'].values
        if 'production_line' in df_featured.columns:
            order_result['production_line'] = df_featured['production_line'].values
        order_result['predicted_tpt_days'] = np.round(y_pred, 2)
        if 'actual_production_days' in df_featured.columns:
            order_result['actual_tpt_days'] = df_featured['actual_production_days'].values

        # ---- 按物料聚合 ----
        agg_func = 'median' if 'median' in agg_method else 'mean'
        agg_label = '中位数' if agg_func == 'median' else '均值'

        mat_agg = order_result.groupby('material').agg(
            predicted_tpt=pd.NamedAgg('predicted_tpt_days', agg_func),
            order_count=pd.NamedAgg('predicted_tpt_days', 'count'),
            tpt_std=pd.NamedAgg('predicted_tpt_days', 'std'),
            tpt_min=pd.NamedAgg('predicted_tpt_days', 'min'),
            tpt_max=pd.NamedAgg('predicted_tpt_days', 'max'),
        ).reset_index()
        mat_agg['predicted_tpt'] = np.round(mat_agg['predicted_tpt'], 2)
        mat_agg['tpt_std'] = np.round(mat_agg['tpt_std'].fillna(0), 2)

        # 附加物料描述和产线
        desc_map = order_result.drop_duplicates('material').set_index('material')
        if 'material_description' in desc_map.columns:
            mat_agg['material_description'] = mat_agg['material'].map(desc_map['material_description'])
        if 'production_line' in desc_map.columns:
            mat_agg['production_line'] = mat_agg['material'].map(desc_map['production_line'])

        # 附加 FG 当前 TPT 值（用于对比）
        fg_path = _Path(data_dir) / "FG.csv"
        if fg_path.exists():
            fg_df = pd.read_csv(fg_path, encoding="utf-8")
            fg_col_map = {'Material': 'material', 'Total Production Time': 'current_tpt'}
            fg_df = fg_df.rename(columns=fg_col_map)
            if 'current_tpt' in fg_df.columns:
                fg_tpt = fg_df.groupby('material')['current_tpt'].first()
                mat_agg['current_tpt'] = mat_agg['material'].map(fg_tpt)
                mat_agg['tpt_change'] = np.round(mat_agg['predicted_tpt'] - mat_agg['current_tpt'].fillna(0), 2)

        # 如有实际数据，计算物料级实际 TPT 均值
        if 'actual_tpt_days' in order_result.columns and order_result['actual_tpt_days'].notna().sum() > 0:
            actual_mat = order_result.groupby('material')['actual_tpt_days'].agg(agg_func).round(2)
            mat_agg['actual_tpt'] = mat_agg['material'].map(actual_mat)

        progress.progress(90, text="物料聚合完成")

        # ---- 保存 ----
        pred_dir = _Path("predictions"); pred_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = pred_dir / f"material_tpt_{ts}.csv"
        mat_agg.to_csv(out_path, index=False, encoding="utf-8")
        mat_agg.to_csv(pred_dir / "material_tpt_latest.csv", index=False, encoding="utf-8")
        order_result.to_csv(pred_dir / "order_tpt_latest.csv", index=False, encoding="utf-8")

        progress.progress(100, text="✅ 预测完成")

        # ---- 展示 ----
        _display_tpt_results(mat_agg, agg_label, out_path, order_df=order_result, widget_key="live")

    except Exception as e:
        progress.progress(0, text="❌ 失败")
        st.error(f"TPT 预测失败: {e}")
        import traceback
        st.code(traceback.format_exc(), language="text")


def _generate_material_summary(row: pd.Series, global_median: float, agg_label: str) -> str:
    """
    针对单颗物料的预测结果，结合算法逻辑生成结构化 Markdown 解释（用于界面展示）。
    输入：mat_agg 的一行 + 全局中位数 + 聚合方式标签
    输出：Markdown 字符串（五段结构）
    """
    pred    = float(row['predicted_tpt'])
    cnt     = int(row['order_count'])
    std     = float(row.get('tpt_std', 0) or 0)
    tpt_min = float(row['tpt_min'])
    tpt_max = float(row['tpt_max'])
    span    = tpt_max - tpt_min
    cv      = std / pred if pred > 0.01 else 0.0

    # ------- 【预测结论】判断 -------
    diff_vs_global = pred - global_median
    diff_pct = diff_vs_global / global_median * 100 if global_median > 0 else 0.0
    if diff_pct > 20:
        concl_icon, concl_label = "🔴", "偏慢物料"
        concl_reason = "模型判断该物料在本批次订单特征下（工期计划、排程等待、历史均值等）倾向于比全局水平更慢完成生产。"
    elif diff_pct < -20:
        concl_icon, concl_label = "🟢", "偏快物料"
        concl_reason = "模型判断该物料在本批次订单特征下倾向于比全局水平更快完成生产。"
    else:
        concl_icon, concl_label = "🟡", "正常物料"
        concl_reason = "预测 TPT 与全局水平接近，生产周期预计无明显异常。"

    diff_str = (f"比全局{agg_label} {global_median:.2f} 天偏长 **{diff_vs_global:+.2f} 天（{diff_pct:+.1f}%）**"
                if diff_pct >= 0 else
                f"比全局{agg_label} {global_median:.2f} 天偏短 **{abs(diff_vs_global):.2f} 天（{diff_pct:.1f}%）**")

    section_conclusion = f"""{concl_icon} **【预测结论】**
模型对该物料的 **{cnt}** 张工单分别评分，取{agg_label}后代表性生产周期为 **{pred:.2f} 天**，{diff_str}，属于 **{concl_label}**。{concl_reason}"""

    # ------- 【批次特征】 -------
    if cnt <= 2:
        cnt_eval = f"样本量极少（仅 {cnt} 张），单张工单特征对聚合值影响极大，结论可信度低。建议待更多工单入库后再确认。"
    elif cnt <= 9:
        cnt_eval = f"样本量中等（{cnt} 张），{agg_label}有一定代表性，但若其中存在极端工单（如大批量或缺料），聚合值仍可能偏移。"
    else:
        cnt_eval = f"样本量充足（{cnt} 张），{agg_label}统计意义较强，单张工单的特殊情况对聚合值影响有限。"

    section_batch = f"""📦 **【批次特征】**
本批次共 **{cnt}** 张工单参与预测，{cnt_eval}"""

    # ------- 【预测稳定性 & 区间】 -------
    if cv < 0.15:
        stability_label, stability_icon = "稳定", "🟢"
        stability_advice = f"各张工单的生产特征高度一致，可直接使用 {pred:.2f} 天作为排产依据。"
    elif cv < 0.30:
        stability_label, stability_icon = "中等波动", "🟡"
        stability_advice = f"批次内存在一定差异，建议在 {pred:.2f} 天基础上保留 1 天左右缓冲。"
    else:
        stability_label, stability_icon = "高度分散", "🔴"
        stability_advice = f"批次内工单差异显著，**不建议直接使用 {pred:.2f} 天作为统一排产依据，应按工单逐一安排产能。**"

    span_warn = ""
    if span > pred * 0.5:
        span_warn = f"\n> ⚠️ 区间跨度 **{span:.2f} 天** 超过预测值的 50%（警戒线：{pred*0.5:.2f} 天），说明同物料不同工单之间的生产效率或等待时间存在显著差异。"

    section_stability = f"""{stability_icon} **【预测稳定性 & 区间】**
标准差为 **{std:.2f} 天**，变异系数（CV）= {cv*100:.1f}%，属于 **{stability_label}**。
最快工单预测 **{tpt_min:.2f} 天**（乐观情形），最慢 **{tpt_max:.2f} 天**（保守情形），区间跨度 **{span:.2f} 天**。
{stability_advice}{span_warn}"""

    # ------- 【变化趋势】（有 current_tpt 时生成）-------
    section_change = ""
    has_current = 'current_tpt' in row.index and pd.notna(row.get('current_tpt'))
    if has_current:
        cur = float(row['current_tpt'])
        chg = pred - cur
        chg_pct = chg / cur * 100 if cur > 0.01 else 0.0
        if chg > 0.5:
            chg_icon = "🔺"
            chg_interp = f"模型预测值比 FG 系统登记值高 **{chg:+.2f} 天（{chg_pct:+.1f}%）**，可能说明近期排程等待或批量特征比历史登记值更复杂，建议核查是否存在产能瓶颈或物料缺货。"
        elif chg < -0.5:
            chg_icon = "🔻"
            chg_interp = f"模型预测值比 FG 系统登记值低 **{abs(chg):.2f} 天（{chg_pct:.1f}%）**，可能说明近期生产效率提升或排队等待减少。如趋势稳定，建议评估是否下调 FG 参数。"
        else:
            chg_icon = "➡️"
            chg_interp = f"模型预测值与 FG 系统登记值基本一致（偏差 {chg:+.2f} 天），当前 FG 参数与实际生产节奏吻合，无需调整。"
        section_change = f"""{chg_icon} **【变化趋势】**
FG 系统当前登记 TPT = **{cur:.2f} 天**，模型预测 {pred:.2f} 天。{chg_interp}"""

    # ------- 【实际对比验证】（有 actual_tpt 时生成）-------
    section_actual = ""
    has_actual = 'actual_tpt' in row.index and pd.notna(row.get('actual_tpt'))
    if has_actual:
        act = float(row['actual_tpt'])
        err = pred - act
        err_pct = err / act * 100 if act > 0.01 else 0.0
        if abs(err_pct) <= 10:
            acc_icon, acc_label = "✅", "预测准确"
            acc_advice = "模型对该物料的预测偏差在 10% 以内，可信度高。"
        elif abs(err_pct) <= 20:
            acc_icon, acc_label = "🟡", "中等偏差"
            acc_advice = ("模型偏高估了实际生产周期，排产时可在预测值基础上适当压缩。" if err > 0
                          else "模型低估了实际生产周期，排产时建议增加缓冲天数。")
        else:
            acc_icon, acc_label = "🔴", "偏差较大"
            acc_advice = ("模型显著高估，可能该物料的近期工单特征与训练数据存在分布偏移，建议在下次建模时重新纳入最新数据。" if err > 0
                          else "模型显著低估，该物料实际耗时远超预测，建议检查是否有未纳入模型的延误因素（如外协、检验等待等）。")
        section_actual = f"""{acc_icon} **【实际对比验证】**
历史实绩 actual_tpt = **{act:.2f} 天**，模型预测 {pred:.2f} 天，误差 **{err:+.2f} 天（{err_pct:+.1f}%）**，评级：**{acc_label}**。{acc_advice}"""

    # ------- 拼装 -------
    parts = [section_conclusion, section_batch, section_stability]
    if section_change:
        parts.append(section_change)
    if section_actual:
        parts.append(section_actual)

    return "\n\n".join(parts)


def _build_material_export_dict(row: pd.Series, global_median: float, agg_label: str) -> dict:
    """
    生成单颗物料的 JSON 导出字典（人类可读格式，material_number 作为外部 key）。
    """
    pred    = float(row['predicted_tpt'])
    cnt     = int(row['order_count'])
    std     = float(row.get('tpt_std', 0) or 0)
    tpt_min = float(row['tpt_min'])
    tpt_max = float(row['tpt_max'])
    span    = round(tpt_max - tpt_min, 2)
    cv      = round(std / pred * 100, 1) if pred > 0.01 else 0.0

    diff_vs_global = round(pred - global_median, 2)
    diff_pct = round(diff_vs_global / global_median * 100, 1) if global_median > 0 else 0.0
    if diff_pct > 20:
        concl_label = "偏慢物料"
        concl_text = (f"模型对该物料的 {cnt} 张工单分别评分，取{agg_label}后代表性生产周期为 {pred:.2f} 天，"
                      f"比全局{agg_label} {global_median:.2f} 天偏长 {diff_vs_global:+.2f} 天（{diff_pct:+.1f}%），"
                      f"属于 {concl_label}。模型判断该物料在本批次订单特征下（工期计划、排程等待、历史均值等）"
                      f"倾向于比全局水平更慢完成生产。")
    elif diff_pct < -20:
        concl_label = "偏快物料"
        concl_text = (f"模型对该物料的 {cnt} 张工单分别评分，取{agg_label}后代表性生产周期为 {pred:.2f} 天，"
                      f"比全局{agg_label} {global_median:.2f} 天偏短 {abs(diff_vs_global):.2f} 天（{diff_pct:.1f}%），"
                      f"属于 {concl_label}。模型判断该物料在本批次订单特征下倾向于比全局水平更快完成生产。")
    else:
        concl_label = "正常物料"
        concl_text = (f"模型对该物料的 {cnt} 张工单分别评分，取{agg_label}后代表性生产周期为 {pred:.2f} 天，"
                      f"比全局{agg_label} {global_median:.2f} 天偏差 {diff_vs_global:+.2f} 天（{diff_pct:+.1f}%），"
                      f"属于 {concl_label}。预测 TPT 与全局水平接近，生产周期预计无明显异常。")

    if cnt <= 2:
        batch_text = (f"本批次共 {cnt} 张工单参与预测，样本量极少（仅 {cnt} 张），"
                      f"单张工单特征对聚合值影响极大，结论可信度低。建议待更多工单入库后再确认。")
    elif cnt <= 9:
        batch_text = (f"本批次共 {cnt} 张工单参与预测，样本量中等（{cnt} 张），"
                      f"{agg_label}有一定代表性，但若其中存在极端工单（如大批量或缺料），聚合值仍可能偏移。")
    else:
        batch_text = (f"本批次共 {cnt} 张工单参与预测，样本量充足（{cnt} 张），"
                      f"{agg_label}统计意义较强，单张工单的特殊情况对聚合值影响有限。")

    if cv < 15:
        stability_rating = "稳定"
        stability_advice = f"各张工单的生产特征高度一致，可直接使用 {pred:.2f} 天作为排产依据。"
    elif cv < 30:
        stability_rating = "中等波动"
        stability_advice = f"批次内存在一定差异，建议在 {pred:.2f} 天基础上保留 1 天左右缓冲。"
    else:
        stability_rating = "高度分散"
        stability_advice = f"批次内工单差异显著，不建议直接使用 {pred:.2f} 天作为统一排产依据，应按工单逐一安排产能。"

    stability_dict = {
        "标准差": f"{std:.2f} 天",
        "变异系数_CV": f"{cv:.1f}%",
        "稳定性评级": stability_rating,
        "最快工单预测_乐观": f"{tpt_min:.2f} 天",
        "最慢工单预测_保守": f"{tpt_max:.2f} 天",
        "区间跨度": f"{span:.2f} 天",
        "建议": stability_advice,
    }
    if span > pred * 0.5:
        stability_dict["风险提示"] = (f"区间跨度 {span:.2f} 天超过预测值的 50%（警戒线：{pred*0.5:.2f} 天），"
                                       f"说明同物料不同工单之间的生产效率或等待时间存在显著差异。")

    result = {
        "预测结论": concl_text,
        "批次特征": batch_text,
        "预测稳定性_区间": stability_dict,
    }

    has_current = 'current_tpt' in row.index and pd.notna(row.get('current_tpt'))
    if has_current:
        cur = float(row['current_tpt'])
        chg = round(pred - cur, 2)
        chg_pct = round(chg / cur * 100, 1) if cur > 0.01 else 0.0
        if chg > 0.5:
            chg_text = (f"模型预测值比 FG 系统登记值高 {chg:+.2f} 天（{chg_pct:+.1f}%），"
                        f"可能说明近期排程等待或批量特征比历史登记值更复杂，建议核查是否存在产能瓶颈或物料缺货。")
        elif chg < -0.5:
            chg_text = (f"模型预测值比 FG 系统登记值低 {abs(chg):.2f} 天（{chg_pct:.1f}%），"
                        f"可能说明近期生产效率提升或排队等待减少。如趋势稳定，建议评估是否下调 FG 参数。")
        else:
            chg_text = (f"模型预测值与 FG 系统登记值基本一致（偏差 {chg:+.2f} 天），"
                        f"当前 FG 参数与实际生产节奏吻合，无需调整。")
        result["变化趋势"] = {
            "FG当前TPT": f"{cur:.2f} 天",
            "模型预测TPT": f"{pred:.2f} 天",
            "变化量": f"{chg:+.2f} 天（{chg_pct:+.1f}%）",
            "说明": chg_text,
        }

    has_actual = 'actual_tpt' in row.index and pd.notna(row.get('actual_tpt'))
    if has_actual:
        act = float(row['actual_tpt'])
        err = round(pred - act, 2)
        err_pct = round(err / act * 100, 1) if act > 0.01 else 0.0
        if abs(err_pct) <= 10:
            acc_rating = "预测准确"
            acc_text = f"历史实绩 {act:.2f} 天，模型预测 {pred:.2f} 天，误差 {err:+.2f} 天（{err_pct:+.1f}%），偏差在 10% 以内，可信度高。"
        elif abs(err_pct) <= 20:
            acc_rating = "中等偏差"
            acc_text = (f"历史实绩 {act:.2f} 天，模型预测 {pred:.2f} 天，误差 {err:+.2f} 天（{err_pct:+.1f}%）。"
                        + ("模型偏高估，排产时可在预测值基础上适当压缩。" if err > 0 else "模型低估了实际生产周期，排产时建议增加缓冲天数。"))
        else:
            acc_rating = "偏差较大"
            acc_text = (f"历史实绩 {act:.2f} 天，模型预测 {pred:.2f} 天，误差 {err:+.2f} 天（{err_pct:+.1f}%）。"
                        + ("模型显著高估，可能该物料近期工单特征与训练数据存在分布偏移，建议在下次建模时重新纳入最新数据。" if err > 0
                           else "模型显著低估，建议检查是否有未纳入模型的延误因素（如外协、检验等待等）。"))
        result["实际对比验证"] = {
            "历史实绩TPT": f"{act:.2f} 天",
            "模型预测TPT": f"{pred:.2f} 天",
            "误差": f"{err:+.2f} 天（{err_pct:+.1f}%）",
            "评级": acc_rating,
            "说明": acc_text,
        }

    return result


def _display_tpt_results(mat_agg: pd.DataFrame, agg_label: str, out_path,
                         order_df: pd.DataFrame = None, widget_key: str = "live"):
    """展示物料级 TPT 预测结果"""
    st.markdown("---")
    st.subheader("📊 物料 TPT 预测结果")

    # ---- 预生成每颗物料的算法解释 summary ----
    _global_median = float(mat_agg['predicted_tpt'].median())
    mat_agg = mat_agg.copy()
    mat_agg['summary'] = mat_agg.apply(
        lambda r: _generate_material_summary(r, _global_median, agg_label), axis=1
    )

    # ---- 概览指标 ----
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("物料数量", f"{len(mat_agg):,}")
    with c2:
        st.metric(f"平均预测 TPT ({agg_label})", f"{mat_agg['predicted_tpt'].mean():.1f} 天")
    with c3:
        st.metric("总工单数", f"{mat_agg['order_count'].sum():,}")
    has_current = 'current_tpt' in mat_agg.columns and mat_agg['current_tpt'].notna().sum() > 0
    with c4:
        if has_current:
            changed = (mat_agg['tpt_change'].abs() > 0.5).sum()
            st.metric("TPT 变化物料数", f"{changed}", help="预测 TPT 与 FG 当前值偏差 > 0.5 天")
        else:
            st.metric("TPT 标准差均值", f"{mat_agg['tpt_std'].mean():.2f} 天")

    # ---- 预测 vs 实际（如有） ----
    if 'actual_tpt' in mat_agg.columns and mat_agg['actual_tpt'].notna().sum() > 1:
        st.subheader("📈 预测 vs 实际（物料级）")
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
        valid = mat_agg['actual_tpt'].notna()
        rmse = float(np.sqrt(mean_squared_error(mat_agg.loc[valid, 'actual_tpt'], mat_agg.loc[valid, 'predicted_tpt'])))
        mae = float(mean_absolute_error(mat_agg.loc[valid, 'actual_tpt'], mat_agg.loc[valid, 'predicted_tpt']))
        r2 = float(r2_score(mat_agg.loc[valid, 'actual_tpt'], mat_agg.loc[valid, 'predicted_tpt']))
        mc1, mc2, mc3 = st.columns(3)
        with mc1: st.metric("RMSE", f"{rmse:.3f} 天")
        with mc2: st.metric("MAE", f"{mae:.3f} 天")
        with mc3: st.metric("R²", f"{r2:.4f}")
        _explain_metrics(rmse=rmse, mae=mae, r2=r2)

    # ---- 当前 TPT vs 预测 TPT 对比图 ----
    if has_current:
        st.subheader("📊 当前 TPT vs 预测 TPT")
        cmp = mat_agg[mat_agg['current_tpt'].notna()].sort_values('predicted_tpt', ascending=False).head(30)
        if len(cmp) > 0:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=cmp['material'], y=cmp['current_tpt'],
                name='当前 TPT (FG)', marker_color='#95a5a6',
            ))
            fig.add_trace(go.Bar(
                x=cmp['material'], y=cmp['predicted_tpt'],
                name='预测 TPT', marker_color='#3498db',
            ))
            fig.update_layout(
                barmode='group', height=420, template="plotly_white",
                xaxis_title="物料", yaxis_title="TPT (天)",
                xaxis_tickangle=-45,
            )
            st.plotly_chart(fig, use_container_width=True)

    # ---- 指标计算说明 ----
    with st.expander("💡 如何读懂这些预测指标？", expanded=False):
        st.markdown(f"""
**这些指标是怎么算出来的？**

模型对每张生产工单**独立**预测一个 `predicted_tpt_days`，再对同物料的所有工单聚合，得到：

| 列名 | 计算方法 | 含义 |
|:-----|:--------|:-----|
| **predicted_tpt** | 所有工单预测值的 **{agg_label}** | 该物料本批次的代表性生产周期 |
| **tpt_std** | 所有工单预测值的 **标准差** | 越大说明批次内不同工单差异越大 |
| **tpt_min** | 所有工单预测值的 **最小值** | 最快工单的预测天数（乐观情形） |
| **tpt_max** | 所有工单预测值的 **最大值** | 最慢工单的预测天数（保守情形） |

**为什么 predicted_tpt 靠近 tpt_min 或 tpt_max？**

模型根据每张工单的特征值（计划工期、历史均值、排程等待天数、缺料状态等）独立给出预测分数。聚合到物料级时：

- 🟢 **靠近 tpt_min**：本批多数工单计划工期短、排队等待少、历史实绩快，模型对大多数工单给出了较低的预测值
- 🟡 **居中**：批次内工单差异均匀，{agg_label}自然落在中间位置
- 🔴 **靠近 tpt_max**：存在大批量、排程瓶颈或历史偏慢的工单主导了聚合结果

> 💡 **tpt_std 越大**，说明同物料不同工单间预测差异明显，建议按工单分别安排产能而非直接使用物料汇总值。
""")

    # ---- 物料 TPT 明细表 ----
    st.subheader("📋 物料 TPT 明细")
    display_cols = ['material']
    if 'material_description' in mat_agg.columns:
        display_cols.append('material_description')
    if 'production_line' in mat_agg.columns:
        display_cols.append('production_line')
    display_cols.extend(['predicted_tpt', 'order_count', 'tpt_std', 'tpt_min', 'tpt_max'])
    if has_current:
        display_cols.extend(['current_tpt', 'tpt_change'])
    if 'actual_tpt' in mat_agg.columns:
        display_cols.append('actual_tpt')
    display_cols = [c for c in display_cols if c in mat_agg.columns]

    fmt = {'predicted_tpt': '{:.2f}', 'tpt_std': '{:.2f}', 'tpt_min': '{:.1f}', 'tpt_max': '{:.1f}'}
    if has_current:
        fmt['current_tpt'] = '{:.1f}'
        fmt['tpt_change'] = '{:+.2f}'
    if 'actual_tpt' in mat_agg.columns:
        fmt['actual_tpt'] = '{:.1f}'

    st.dataframe(
        mat_agg[display_cols].sort_values('predicted_tpt', ascending=False).style.format(fmt),
        use_container_width=True, height=500,
    )

    # ---- 单物料工单 TPT 分布图 ----
    st.subheader("📈 工单 TPT 分布 — 按物料查看")
    st.caption("在下拉框中选择物料，查看该物料所有工单的预测 TPT 分布直方图。绿色虚线 = tpt_min，橙色实线 = predicted_tpt（聚合值），红色虚线 = tpt_max。")

    _mat_info = mat_agg.sort_values('order_count', ascending=False).copy()
    _desc_col = 'material_description' if 'material_description' in _mat_info.columns else None
    _mat_labels = {}
    for _, _r in _mat_info.iterrows():
        _label = str(_r['material'])
        if _desc_col and pd.notna(_r.get(_desc_col, '')) and str(_r.get(_desc_col, '')) != '':
            _label += f"  |  {_r[_desc_col]}"
        _label += f"  ({int(_r['order_count'])} 工单)"
        _mat_labels[_r['material']] = _label

    _sel_mat = st.selectbox(
        "选择物料",
        list(_mat_labels.keys()),
        format_func=lambda m: _mat_labels.get(m, str(m)),
        key=f"tpt_dist_mat_sel_{widget_key}",
    )

    if _sel_mat is not None:
        _agg_row = mat_agg[mat_agg['material'] == _sel_mat].iloc[0]
        _tpt_min = float(_agg_row['tpt_min'])
        _tpt_max = float(_agg_row['tpt_max'])
        _pred_tpt = float(_agg_row['predicted_tpt'])
        _tpt_std = float(_agg_row['tpt_std'])
        _order_cnt = int(_agg_row['order_count'])
        _span = _tpt_max - _tpt_min
        _pos_ratio = (_pred_tpt - _tpt_min) / _span if _span > 0.01 else 0.5

        _fig_dist = go.Figure()
        _has_order_data = order_df is not None and _sel_mat in order_df['material'].values

        if _has_order_data:
            _mat_orders = (order_df[order_df['material'] == _sel_mat]
                           .copy()
                           .sort_values('predicted_tpt_days')
                           .reset_index(drop=True))
            _mat_orders['_rank'] = range(1, len(_mat_orders) + 1)

            # ---- 趋势线：LOWESS 平滑（工单数足够时）或直接折线 ----
            _xs = _mat_orders['_rank'].values
            _ys = _mat_orders['predicted_tpt_days'].values
            if len(_xs) >= 6:
                # 用滚动均值作为趋势线（窗口=max(3, N//5)）
                _win = max(3, len(_xs) // 5)
                _trend_y = (pd.Series(_ys)
                            .rolling(_win, center=True, min_periods=1)
                            .mean().values)
            else:
                _trend_y = _ys

            # 点颜色：低于 predicted_tpt → 绿，高于 → 红
            _dot_colors = ['#27ae60' if v <= _pred_tpt else '#e74c3c'
                           for v in _mat_orders['predicted_tpt_days']]

            # 是否有实际 TPT
            _has_actual = ('actual_tpt_days' in _mat_orders.columns
                           and _mat_orders['actual_tpt_days'].notna().sum() > 1)

            # ---- 实际 TPT 散点（若有）----
            if _has_actual:
                _act = _mat_orders.dropna(subset=['actual_tpt_days'])
                _fig_dist.add_trace(go.Scatter(
                    x=_act['_rank'], y=_act['actual_tpt_days'],
                    mode='markers',
                    name='实际 TPT',
                    marker=dict(size=8, color='#2ecc71', symbol='diamond',
                                line=dict(width=1, color='#27ae60')),
                    hovertemplate='工单排序: %{x}<br>实际 TPT: %{y:.1f} 天<extra></extra>',
                ))

            # ---- 所有工单散点 ----
            _fig_dist.add_trace(go.Scatter(
                x=_mat_orders['_rank'], y=_mat_orders['predicted_tpt_days'],
                mode='markers',
                name='工单预测 TPT',
                marker=dict(size=9, color=_dot_colors,
                            line=dict(width=1, color='white')),
                hovertemplate='工单排序（低→高）: %{x}<br>预测 TPT: %{y:.2f} 天<extra></extra>',
            ))

            # ---- 趋势线 ----
            _fig_dist.add_trace(go.Scatter(
                x=_xs, y=_trend_y,
                mode='lines',
                name='趋势线（滚动均值）',
                line=dict(color='#2980b9', width=2.5, dash='solid'),
                hovertemplate='趋势: %{y:.2f} 天<extra></extra>',
            ))

            # ---- tpt_min / tpt_max 端点标注 ----
            _min_idx = int(_mat_orders['_rank'].iloc[0])
            _max_idx = int(_mat_orders['_rank'].iloc[-1])
            _fig_dist.add_trace(go.Scatter(
                x=[_min_idx, _max_idx],
                y=[_tpt_min, _tpt_max],
                mode='markers+text',
                name='min / max 工单',
                marker=dict(size=14, color=['#27ae60', '#e74c3c'], symbol='circle-open',
                            line=dict(width=2.5)),
                text=[f'最低 {_tpt_min:.1f}d', f'最高 {_tpt_max:.1f}d'],
                textposition=['bottom center', 'top center'],
                textfont=dict(size=11),
                hovertemplate='%{text}<extra></extra>',
            ))

            # ---- predicted_tpt 高亮带 + 粗实线 + 标注菱形 ----
            # 半透明黄色背景带（±0.3天）
            _fig_dist.add_hrect(
                y0=_pred_tpt - 0.3, y1=_pred_tpt + 0.3,
                fillcolor='rgba(230,126,34,0.12)', line_width=0,
                annotation=None,
            )
            # 粗实线
            _fig_dist.add_hline(
                y=_pred_tpt, line_dash='solid', line_color='#e67e22', line_width=3,
                annotation_text=None,
            )
            # 在图的左侧和右侧各放一个大菱形标注点，使线更醒目
            _fig_dist.add_trace(go.Scatter(
                x=[_xs[0], _xs[-1]],
                y=[_pred_tpt, _pred_tpt],
                mode='markers+text',
                marker=dict(size=16, color='#e67e22', symbol='diamond',
                            line=dict(width=2, color='white')),
                text=[f'◀ {agg_label} {_pred_tpt:.2f}d', ''],
                textposition='middle left',
                textfont=dict(size=12, color='#e67e22'),
                name=f'predicted_tpt ({agg_label})',
                hovertemplate=f'{agg_label}: {_pred_tpt:.2f} 天<extra></extra>',
                showlegend=True,
            ))

            _n_low  = int((_mat_orders['predicted_tpt_days'] <= _pred_tpt).sum())
            _n_high = _order_cnt - _n_low

            _fig_dist.update_layout(
                height=400, template='plotly_white',
                title=dict(
                    text=(f"<b>{_mat_labels.get(_sel_mat, _sel_mat)}</b>  "
                          f"<span style='font-size:13px;color:#7f8c8d'>"
                          f"共 {_order_cnt} 张工单  |  std={_tpt_std:.2f}d</span>"),
                    font_size=14),
                xaxis_title='工单排序（按预测 TPT 从低到高）',
                yaxis_title='预测 TPT（天）',
                legend=dict(orientation='h', y=1.10, x=0, bgcolor='rgba(0,0,0,0)'),
                margin=dict(t=70, b=40, l=20, r=20),
            )
            st.plotly_chart(_fig_dist, use_container_width=True)

        else:
            _n_low = _order_cnt // 2
            _n_high = _order_cnt - _n_low
            st.info("无工单级数据，请重新运行预测以获取散点图。")

        if _pos_ratio <= 0.33:
            _pos_icon, _pos_text = "🟢", f"偏乐观：多数工单预测偏低（{_n_low}/{_order_cnt} 张 ≤ {agg_label}），{agg_label}落在区间左侧"
        elif _pos_ratio >= 0.67:
            _pos_icon, _pos_text = "🔴", f"偏保守：较多工单预测偏高（{_n_high}/{_order_cnt} 张 > {agg_label}），{agg_label}落在区间右侧"
        else:
            _pos_icon, _pos_text = "🟡", f"居中：工单预测分布较均匀（低于{agg_label} {_n_low} 张 / 高于 {_n_high} 张）"
        st.caption(
            f"{_pos_icon} **区间位置 {_pos_ratio*100:.0f}%**（tpt_min=0%，tpt_max=100%） — {_pos_text}。"
            + (f"  标准差 {_tpt_std:.2f} 天（批次内差异较大，建议逐工单排产）" if _tpt_std > 1.5 else f"  标准差 {_tpt_std:.2f} 天")
        )

    # ---- 物料算法逻辑解释 ----
    st.markdown("---")
    st.subheader("🧠 物料预测逻辑解释")
    st.caption("选择一颗物料，查看模型针对该物料数据给出的算法逻辑解释（包含预测结论、批次特征、稳定性分析、与 FG 值对比、实际误差验证）。")

    _summary_mat_info = mat_agg.sort_values('order_count', ascending=False).copy()
    _summary_desc_col = 'material_description' if 'material_description' in _summary_mat_info.columns else None
    _summary_labels = {}
    for _, _sr in _summary_mat_info.iterrows():
        _slabel = str(_sr['material'])
        if _summary_desc_col and pd.notna(_sr.get(_summary_desc_col, '')) and str(_sr.get(_summary_desc_col, '')) != '':
            _slabel += f"  |  {_sr[_summary_desc_col]}"
        _slabel += f"  ({int(_sr['order_count'])} 工单)"
        _summary_labels[_sr['material']] = _slabel

    _sel_summary_mat = st.selectbox(
        "选择物料查看算法解释",
        list(_summary_labels.keys()),
        format_func=lambda m: _summary_labels.get(m, str(m)),
        key=f"summary_mat_sel_{widget_key}",
    )

    if _sel_summary_mat is not None:
        _sumrow = mat_agg[mat_agg['material'] == _sel_summary_mat].iloc[0]
        _pred_v   = float(_sumrow['predicted_tpt'])
        _cnt_v    = int(_sumrow['order_count'])
        _std_v    = float(_sumrow.get('tpt_std', 0) or 0)
        _min_v    = float(_sumrow['tpt_min'])
        _max_v    = float(_sumrow['tpt_max'])
        _cv_v     = _std_v / _pred_v * 100 if _pred_v > 0 else 0

        # 风险标签
        _risk_factors = []
        if _cv_v > 30:
            _risk_factors.append("批次内分散")
        if _cnt_v <= 2:
            _risk_factors.append("样本不足")
        has_act_col = 'actual_tpt' in _sumrow.index and pd.notna(_sumrow.get('actual_tpt'))
        if has_act_col:
            _err_pct = abs(_pred_v - float(_sumrow['actual_tpt'])) / float(_sumrow['actual_tpt']) * 100
            if _err_pct > 20:
                _risk_factors.append(f"历史误差偏大({_err_pct:.0f}%)")
        if has_current and pd.notna(_sumrow.get('current_tpt')) and abs(_pred_v - float(_sumrow['current_tpt'])) > 2:
            _risk_factors.append("与FG值偏差显著")

        if _risk_factors:
            st.warning(f"⚠️ 风险提示：{' · '.join(_risk_factors)}", icon=None)
        else:
            st.success("✅ 该物料预测结论可信度正常，无风险标记。")

        # 数据概要卡片
        _kc1, _kc2, _kc3, _kc4, _kc5 = st.columns(5)
        with _kc1: st.metric("predicted_tpt", f"{_pred_v:.2f} 天")
        with _kc2: st.metric("order_count", f"{_cnt_v}")
        with _kc3: st.metric("tpt_std (CV)", f"{_std_v:.2f} 天 ({_cv_v:.0f}%)")
        with _kc4: st.metric("tpt_min → tpt_max", f"{_min_v:.1f} → {_max_v:.1f} 天")
        with _kc5:
            if has_act_col:
                st.metric("actual_tpt", f"{float(_sumrow['actual_tpt']):.2f} 天")
            elif has_current and pd.notna(_sumrow.get('current_tpt')):
                st.metric("current_tpt (FG)", f"{float(_sumrow['current_tpt']):.2f} 天")
            else:
                st.metric("全局中位数", f"{_global_median:.2f} 天")

        # 结构化解释正文
        with st.expander("📖 查看完整算法逻辑解释", expanded=True):
            st.markdown(_sumrow['summary'])

    # ---- 下载 ----
    # 完整数据 CSV（含 summary 文本列）
    csv_bytes = mat_agg.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ 下载物料 TPT 预测 CSV（含逻辑解释）", csv_bytes,
                       file_name=out_path.name, mime="text/csv")

    # 算法逻辑解释 JSON（material_number 为 key，人类可读结构）
    import json as _json
    _export_dict = {
        str(r['material']): _build_material_export_dict(r, _global_median, agg_label)
        for _, r in mat_agg.iterrows()
    }
    _json_bytes = _json.dumps(_export_dict, ensure_ascii=False, indent=2).encode("utf-8")
    _json_filename = out_path.stem + "_summary.json"
    st.download_button("⬇️ 下载算法逻辑解释 JSON（material_number 为 key）", _json_bytes,
                       file_name=_json_filename, mime="application/json")


def _show_latest_tpt_predictions():
    """展示最近一次物料级 TPT 预测结果（从磁盘读取）"""
    pred_path = _Path("predictions") / "material_tpt_latest.csv"
    if not pred_path.exists():
        return

    mtime = datetime.fromtimestamp(pred_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    st.markdown("---")
    st.subheader(f"📋 最近一次 TPT 预测结果（{mtime}）")
    try:
        df = pd.read_csv(pred_path, encoding="utf-8")
        _order_path = _Path("predictions") / "order_tpt_latest.csv"
        _order_df = pd.read_csv(_order_path, encoding="utf-8") if _order_path.exists() else None
        _display_tpt_results(df, agg_label="中位数", out_path=pred_path, order_df=_order_df, widget_key="disk")
    except Exception as e:
        st.error(f"读取失败: {e}")


# ======================================================================
# Token 持久化
# ======================================================================

def _save_connection_config(token: str, endpoint: str, sap_client: str, plant: str):
    """将所有 SAP 连接配置写入项目根目录 .env 文件并更新当前进程环境变量"""
    env_path = _Path(__file__).parent.parent / ".env"

    updates = {
        "SAP_OPENSQL_TOKEN": token,
        "SAP_OPENSQL_ENDPOINT": endpoint,
        "SAP_OPENSQL_CLIENT": sap_client,
        "SAP_OPENSQL_PLANT": plant,
    }

    lines: list[str] = []
    found_keys: set[str] = set()

    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                key = line.split("=", 1)[0].strip()
                if key in updates:
                    lines.append(f"{key}={updates[key]}\n")
                    found_keys.add(key)
                else:
                    lines.append(line)

    for key, val in updates.items():
        if key not in found_keys:
            lines.append(f"{key}={val}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    for key, val in updates.items():
        os.environ[key] = val


def _save_token_to_env(token: str):
    """向后兼容：仅更新 Token（新代码请使用 _save_connection_config）"""
    _save_connection_config(
        token=token,
        endpoint=os.environ.get("SAP_OPENSQL_ENDPOINT", ""),
        sap_client=os.environ.get("SAP_OPENSQL_CLIENT", ""),
        plant=os.environ.get("SAP_OPENSQL_PLANT", ""),
    )


# ======================================================================
# 磁盘数据状态展示（折叠）
# ======================================================================

def _show_data_on_disk(data_dir: str):
    """读取 data/raw 中的 CSV 文件信息，折叠展示"""
    raw_dir = _Path(data_dir)
    file_defs = [
        ("FG.csv", "📦", "成品物料主数据"),
        ("Capacity.csv", "⚙️", "产线产能"),
        ("History.csv", "📜", "生产订单历史"),
        ("Shortage.csv", "🔧", "缺料数据"),
    ]

    with st.expander("📂 当前训练数据状态（data/raw）", expanded=False):
        # 汇总行
        summary_cols = st.columns(4)
        for i, (fname, icon, desc) in enumerate(file_defs):
            fpath = raw_dir / fname
            with summary_cols[i]:
                if fpath.exists():
                    size_mb = fpath.stat().st_size / 1024 / 1024
                    mtime = datetime.fromtimestamp(fpath.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    # 快速读行数（只读索引列）
                    try:
                        nrows = sum(1 for _ in open(fpath, encoding="utf-8")) - 1
                    except Exception:
                        nrows = "?"
                    st.metric(f"{icon} {fname}", f"{nrows:,} 行" if isinstance(nrows, int) else nrows)
                    st.caption(f"{size_mb:.1f} MB · {mtime}")
                else:
                    st.metric(f"{icon} {fname}", "❌ 不存在")

        # 数据预览 tab
        existing = [(fname, icon, desc) for fname, icon, desc in file_defs if (raw_dir / fname).exists()]
        if existing:
            tabs = st.tabs([f"{icon} {fname}" for fname, icon, desc in existing])
            for tab, (fname, icon, desc) in zip(tabs, existing):
                with tab:
                    try:
                        df = pd.read_csv(raw_dir / fname, nrows=15, encoding="utf-8")
                        st.caption(f"{desc} — 前 15 行预览")
                        st.dataframe(df, use_container_width=True, height=300)
                    except Exception as e:
                        st.error(f"读取 {fname} 失败: {e}")


def _show_latest_training_on_disk():
    """从 predictions/ 目录读取最新训练结果并折叠展示"""
    pred_dir = _Path("predictions")
    if not pred_dir.exists():
        return

    # 查找最新的 metrics 文件
    metric_files = sorted(pred_dir.glob("production_time_metrics_*.csv"), reverse=True)
    if not metric_files:
        return

    latest_ts = metric_files[0].stem.replace("production_time_metrics_", "")
    pred_file = pred_dir / f"production_time_predictions_{latest_ts}.csv"
    imp_file = pred_dir / f"production_time_feature_importance_{latest_ts}.csv"

    with st.expander(f"📊 最近训练结果（{latest_ts[:8]}-{latest_ts[8:10]}:{latest_ts[10:12]}:{latest_ts[12:]}）", expanded=False):
        # Metrics
        try:
            metrics_df = pd.read_csv(metric_files[0])
            m = metrics_df.iloc[0].to_dict()

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Test RMSE", f"{m.get('test_rmse', 0):.3f} 天")
            with c2:
                st.metric("Test MAE", f"{m.get('test_mae', 0):.3f} 天")
            with c3:
                st.metric("Test R²", f"{m.get('test_r2', 0):.4f}")
            with c4:
                st.metric("Test SMAPE", f"{m.get('test_smape', m.get('test_mape', 0)):.1f}%")

            _explain_metrics(
                rmse=m.get('test_rmse', 0), mae=m.get('test_mae', 0),
                r2=m.get('test_r2', 0), mape=m.get('test_smape', m.get('test_mape')),
                cv_rmse=m.get('cv_rmse_mean'), cv_r2=m.get('cv_r2_mean'),
            )

            # CV metrics if available
            if 'cv_rmse_mean' in m:
                st.markdown(
                    f"**5-fold TimeSeriesCV**: "
                    f"RMSE **{m['cv_rmse_mean']:.3f} ± {m.get('cv_rmse_std', 0):.3f}** · "
                    f"R² **{m['cv_r2_mean']:.4f} ± {m.get('cv_r2_std', 0):.4f}**"
                )
        except Exception as _e:
            st.warning(f"无法读取指标文件 ({type(_e).__name__}: {_e})")

        # Feature importance
        tab_imp, tab_pred = st.tabs(["🏅 特征重要性", "📋 预测明细"])
        with tab_imp:
            if imp_file.exists():
                try:
                    imp_df = pd.read_csv(imp_file)
                    top15 = imp_df.head(15).sort_values('importance', ascending=True)
                    fig = go.Figure(go.Bar(
                        x=top15['importance'], y=top15['feature'],
                        orientation='h',
                        marker=dict(color=top15['importance'], colorscale='Viridis'),
                        text=[f"{v:.4f}" for v in top15['importance']],
                        textposition='outside',
                    ))
                    fig.update_layout(height=420, template="plotly_white",
                                      xaxis_title="重要性", margin=dict(l=200))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"读取特征重要性失败: {e}")
            else:
                st.info("特征重要性文件不存在")

        with tab_pred:
            if pred_file.exists():
                try:
                    preds = pd.read_csv(pred_file, nrows=50)
                    st.caption(f"前 50 条预测 — 完整文件: `{pred_file.name}`")
                    st.dataframe(preds, use_container_width=True, height=400)
                except Exception as e:
                    st.error(f"读取预测文件失败: {e}")
            else:
                st.info("预测文件不存在")


# ======================================================================
# 模型训练执行
# ======================================================================

def _run_training(data_dir: str, model_params: dict, test_size: float, cv_folds: int,
                  max_wait_days: float = 3.0, use_optuna: bool = False, optuna_trials: int = 50):
    """执行模型训练并展示可视化结果"""
    import importlib
    import src.data_processing.aps_data_loader as _ld_mod
    import src.data_processing.production_time_feature_engineer as _fe_mod
    import src.models.production_time_model as _md_mod
    importlib.reload(_ld_mod)
    importlib.reload(_fe_mod)
    importlib.reload(_md_mod)
    from src.data_processing.aps_data_loader import APSDataLoader
    from src.data_processing.production_time_feature_engineer import ProductionTimeFeatureEngineer
    from src.models.production_time_model import ProductionTimeModel

    progress = st.progress(0, text="正在加载数据...")
    log_area = st.empty()
    logs: list[str] = []

    def _log(msg: str):
        logs.append(f"`{datetime.now().strftime('%H:%M:%S')}` {msg}")
        log_area.markdown("\n\n".join(logs[-10:]))

    try:
        # Step 1: Load data
        _log("📁 加载 CSV 数据...")
        loader = APSDataLoader(data_dir=data_dir)
        df = loader.load_and_merge()
        _log(f"✅ 加载完成: {len(df)} 条生产订单")
        progress.progress(15, text="数据加载完成")

        # Step 2: Feature engineering
        _log("🔧 特征工程（v2）...")
        fe = ProductionTimeFeatureEngineer(lookback_days=90, max_wait_days=max_wait_days)
        df_featured = fe.transform(df)
        feature_cols = fe.get_feature_columns(df_featured)
        _log(f"✅ 特征工程完成: {len(feature_cols)} 个特征, {len(df_featured)} 条样本 (等待过滤≥{max_wait_days}天)")
        progress.progress(35, text="特征工程完成")

        X = df_featured[feature_cols].copy()
        y = df_featured['actual_production_days'].copy()

        split_idx = int(len(X) * (1 - test_size))
        _log(f"📊 数据分割: 训练 {split_idx} 条 ({1-test_size:.0%}) / 测试 {len(X)-split_idx} 条 ({test_size:.0%})")

        # metadata for predictions
        meta_cols = [c for c in [
            'production_number', 'material', 'material_description',
            'order_quantity', 'production_line',
            'planned_start_date', 'planned_finish_date',
            'sales_doc', 'item'
        ] if c in df_featured.columns]
        metadata_df = df_featured[meta_cols].copy()

        # Step 3: Train
        _log("🤖 训练 XGBoost 回归模型（Huber 损失，无对数变换）...")
        model = ProductionTimeModel(model_params=model_params, log_transform=False)

        # P2: Optuna hyperparameter search
        if use_optuna:
            _log(f"🔍 Optuna 调参中（{optuna_trials} 次试验）...")
            progress.progress(45, text=f"Optuna 搜索中...")
            best_params = model.optimize_hyperparams(X, y, n_trials=optuna_trials, n_splits=3)
            _log(f"✅ Optuna 完成 — 最优参数: {best_params}")
            progress.progress(60, text="Optuna 完成，开始训练...")

        metrics, predictions_df = model.train(X, y, test_size=test_size, metadata_df=metadata_df, cv_splits=cv_folds)
        progress.progress(75, text="模型训练完成")
        _log(f"✅ 训练完成 — Test RMSE: {metrics['test_rmse']:.3f}, R²: {metrics['test_r2']:.4f}, SMAPE: {metrics['test_smape']:.1f}%")

        # Step 4: Feature importance
        importance_df = model.get_feature_importance(top_n=20)
        progress.progress(80, text="特征重要性分析完成")

        # Step 5: Save
        _log("💾 保存模型与结果...")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_dir = _Path("models"); model_dir.mkdir(exist_ok=True)
        pred_dir = _Path("predictions"); pred_dir.mkdir(exist_ok=True)

        model.save(str(model_dir / f"production_time_model_{ts}.json"))
        model.save(str(model_dir / "production_time_model_latest.json"))
        predictions_df.to_csv(pred_dir / f"production_time_predictions_{ts}.csv", index=False)
        importance_df.to_csv(pred_dir / f"production_time_feature_importance_{ts}.csv", index=False)

        # Save metrics
        metrics_to_save = {**metrics}
        if model.cv_metrics:
            metrics_to_save.update(model.cv_metrics)
        pd.DataFrame([metrics_to_save]).to_csv(pred_dir / f"production_time_metrics_{ts}.csv", index=False)

        progress.progress(100, text="✅ 全部完成！")
        _log(f"💾 模型已保存: models/production_time_model_{ts}.json")

        # ================================================================
        # 可视化展示
        # ================================================================
        st.markdown("---")
        _show_training_results(metrics, model.cv_metrics, predictions_df, importance_df, y)

    except Exception as e:
        progress.progress(0, text="❌ 训练失败")
        _log(f"❌ 异常: {e}")
        st.error(f"模型训练失败: {e}")
        import traceback
        st.code(traceback.format_exc(), language="text")


def _show_training_results(metrics, cv_metrics, predictions_df, importance_df, y_all):
    """展示训练结果的完整可视化"""

    st.header("📊 训练结果")

    # ------------------------------------------------------------------
    # 1) 核心指标卡片
    # ------------------------------------------------------------------
    st.subheader("🎯 性能指标")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Test RMSE", f"{metrics['test_rmse']:.3f} 天")
    with c2:
        st.metric("Test MAE", f"{metrics['test_mae']:.3f} 天")
    with c3:
        st.metric("Test R²", f"{metrics['test_r2']:.4f}")
    with c4:
        st.metric("Test SMAPE", f"{metrics['test_smape']:.1f}%")

    # Train vs Test 对比
    col_train, col_cv = st.columns(2)
    with col_train:
        st.markdown("**训练集**")
        st.markdown(
            f"RMSE: **{metrics['train_rmse']:.3f}** · "
            f"MAE: **{metrics['train_mae']:.3f}** · "
            f"R²: **{metrics['train_r2']:.4f}**"
        )
    with col_cv:
        if cv_metrics:
            st.markdown("**5-fold TimeSeriesCV**")
            st.markdown(
                f"RMSE: **{cv_metrics['cv_rmse_mean']:.3f} ± {cv_metrics['cv_rmse_std']:.3f}** · "
                f"MAE: **{cv_metrics['cv_mae_mean']:.3f} ± {cv_metrics['cv_mae_std']:.3f}** · "
                f"R²: **{cv_metrics['cv_r2_mean']:.4f} ± {cv_metrics['cv_r2_std']:.4f}**"
            )

    _explain_metrics(
        rmse=metrics['test_rmse'], mae=metrics['test_mae'],
        r2=metrics['test_r2'], mape=metrics['test_smape'],
        cv_rmse=cv_metrics.get('cv_rmse_mean') if cv_metrics else None,
        cv_r2=cv_metrics.get('cv_r2_mean') if cv_metrics else None,
    )

    st.markdown("---")

    # ------------------------------------------------------------------
    # 2) 实际 vs 预测 散点图 + 误差分布
    # ------------------------------------------------------------------
    st.subheader("📈 预测效果分析")
    col_scatter, col_error = st.columns(2)

    actual = predictions_df['actual'].values
    predicted = predictions_df['predicted'].values
    errors = predictions_df['error'].values

    with col_scatter:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=actual, y=predicted,
            mode='markers', marker=dict(size=5, opacity=0.5, color='#3498db'),
            name='测试样本',
        ))
        max_val = max(actual.max(), predicted.max()) + 1
        fig.add_trace(go.Scatter(
            x=[0, max_val], y=[0, max_val],
            mode='lines', line=dict(dash='dash', color='red', width=2),
            name='完美预测线',
        ))
        fig.update_layout(
            title="实际 vs 预测生产天数",
            xaxis_title="实际天数", yaxis_title="预测天数",
            height=420, template="plotly_white",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_error:
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=errors, nbinsx=50,
            marker_color='#2ecc71', opacity=0.8,
            name='误差分布',
        ))
        fig.add_vline(x=0, line_dash="dash", line_color="red")
        mean_err = errors.mean()
        fig.add_vline(x=mean_err, line_dash="dot", line_color="blue",
                      annotation_text=f"Mean={mean_err:.2f}")
        fig.update_layout(
            title="预测误差分布 (实际 - 预测)",
            xaxis_title="误差 (天)", yaxis_title="样本数",
            height=420, template="plotly_white",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------------------------
    # 3) 特征重要性 Top 15
    # ------------------------------------------------------------------
    st.subheader("🏅 特征重要性 Top 15")
    top15 = importance_df.head(15).sort_values('importance', ascending=True)
    fig = go.Figure(go.Bar(
        x=top15['importance'], y=top15['feature'],
        orientation='h',
        marker=dict(color=top15['importance'], colorscale='Viridis'),
        text=[f"{v:.4f}" for v in top15['importance']],
        textposition='outside',
    ))
    fig.update_layout(
        height=480, template="plotly_white",
        xaxis_title="重要性分数", yaxis_title="",
        margin=dict(l=200),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ------------------------------------------------------------------
    # 4) 误差按物料 / 按生产天数区间分析
    # ------------------------------------------------------------------
    st.subheader("🔍 误差深度分析")
    tab_by_range, tab_by_material, tab_table = st.tabs(["按天数区间", "按物料", "预测明细表"])

    with tab_by_range:
        pred_df = predictions_df.copy()
        bins = [0, 1, 3, 5, 10, 999]
        labels = ['0-1天', '1-3天', '3-5天', '5-10天', '10+天']
        pred_df['天数区间'] = pd.cut(pred_df['actual'], bins=bins, labels=labels, right=False)
        range_stats = pred_df.groupby('天数区间', observed=True).agg(
            样本数=('actual', 'count'),
            平均误差=('error', 'mean'),
            MAE=('abs_error', 'mean'),
            RMSE=('error', lambda x: np.sqrt((x**2).mean())),
        ).reset_index()

        col_range_bar, col_range_tbl = st.columns([2, 1])
        with col_range_bar:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=range_stats['天数区间'], y=range_stats['MAE'],
                name='MAE', marker_color='#e74c3c',
            ))
            fig.add_trace(go.Bar(
                x=range_stats['天数区间'], y=range_stats['RMSE'],
                name='RMSE', marker_color='#3498db',
            ))
            fig.update_layout(
                title="各天数区间的预测误差",
                barmode='group', height=380, template="plotly_white",
                yaxis_title="天数",
            )
            st.plotly_chart(fig, use_container_width=True)
        with col_range_tbl:
            st.dataframe(
                range_stats.style.format({'平均误差': '{:.2f}', 'MAE': '{:.2f}', 'RMSE': '{:.2f}'}),
                use_container_width=True, height=380,
            )

    with tab_by_material:
        if 'material' in predictions_df.columns:
            mat_stats = predictions_df.groupby('material').agg(
                样本数=('actual', 'count'),
                实际均值=('actual', 'mean'),
                预测均值=('predicted', 'mean'),
                MAE=('abs_error', 'mean'),
            ).reset_index().sort_values('MAE', ascending=False)

            fig = px.scatter(
                mat_stats.head(30),
                x='实际均值', y='预测均值',
                size='样本数', color='MAE',
                hover_data=['material', '样本数'],
                color_continuous_scale='RdYlGn_r',
                title="各物料的预测准确度（Top 30 MAE）",
            )
            max_v = max(mat_stats['实际均值'].max(), mat_stats['预测均值'].max()) + 1
            fig.add_shape(type="line", x0=0, y0=0, x1=max_v, y1=max_v,
                          line=dict(dash="dash", color="grey"))
            fig.update_layout(height=420, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                mat_stats.head(20).style.format({
                    '实际均值': '{:.2f}', '预测均值': '{:.2f}', 'MAE': '{:.2f}',
                }),
                use_container_width=True,
            )
        else:
            st.info("预测结果中无物料信息")

    with tab_table:
        st.dataframe(
            predictions_df.head(100).style.format({
                'actual': '{:.1f}', 'predicted': '{:.1f}',
                'error': '{:.2f}', 'abs_error': '{:.2f}', 'pct_error': '{:.1f}',
            }),
            use_container_width=True, height=500,
        )

    # ------------------------------------------------------------------
    # 5) 标签分布
    # ------------------------------------------------------------------
    st.subheader("📊 标签分布")
    col_all, col_test = st.columns(2)
    with col_all:
        fig = go.Figure(go.Histogram(
            x=y_all, nbinsx=40, marker_color='#9b59b6', opacity=0.8,
        ))
        fig.update_layout(
            title=f"全量标签分布 (n={len(y_all)}, mean={y_all.mean():.2f}d)",
            xaxis_title="实际生产天数", yaxis_title="样本数",
            height=350, template="plotly_white",
        )
        st.plotly_chart(fig, use_container_width=True)
    with col_test:
        fig = go.Figure(go.Histogram(
            x=actual, nbinsx=40, marker_color='#3498db', opacity=0.8,
        ))
        fig.update_layout(
            title=f"测试集标签分布 (n={len(actual)}, mean={actual.mean():.2f}d)",
            xaxis_title="实际生产天数", yaxis_title="样本数",
            height=350, template="plotly_white",
        )
        st.plotly_chart(fig, use_container_width=True)


# ======================================================================
# 模型测试（加载已训练模型，在测试集上评估）
# ======================================================================

def _run_model_test(data_dir: str, model_path: str, test_size: float,
                    material_filter: list = None, max_days: int = 30):
    """加载已训练模型，在时序测试集上评估（支持筛选）"""
    import importlib
    import src.data_processing.aps_data_loader as _ld_mod
    import src.data_processing.production_time_feature_engineer as _fe_mod
    import src.models.production_time_model as _md_mod
    importlib.reload(_ld_mod); importlib.reload(_fe_mod); importlib.reload(_md_mod)
    from src.data_processing.aps_data_loader import APSDataLoader
    from src.data_processing.production_time_feature_engineer import ProductionTimeFeatureEngineer
    from src.models.production_time_model import ProductionTimeModel
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

    progress = st.progress(0, text="加载数据...")
    try:
        # 1. Load & feature engineer
        loader = APSDataLoader(data_dir=data_dir)
        df = loader.load_and_merge()
        fe = ProductionTimeFeatureEngineer(lookback_days=90)
        df_featured = fe.transform(df)
        feature_cols = fe.get_feature_columns(df_featured)
        progress.progress(30, text="特征工程完成")

        X = df_featured[feature_cols].copy()
        y = df_featured['actual_production_days'].copy()

        # 2. Time-series split
        split_idx = int(len(X) * (1 - test_size))
        X_test = X.iloc[split_idx:].copy()
        y_test = y.iloc[split_idx:].copy()
        meta_cols = [c for c in [
            'production_number', 'material', 'material_description',
            'order_quantity', 'production_line',
            'planned_start_date', 'planned_finish_date',
        ] if c in df_featured.columns]
        meta_test = df_featured[meta_cols].iloc[split_idx:].copy()

        # 3. 应用筛选条件
        keep_mask = pd.Series(True, index=X_test.index)
        if material_filter:
            if 'material' in meta_test.columns:
                keep_mask &= meta_test['material'].isin(material_filter)
        if max_days < 30:
            keep_mask &= (y_test <= max_days)

        X_test = X_test[keep_mask]
        y_test = y_test[keep_mask]
        meta_test = meta_test[keep_mask].reset_index(drop=True)

        if len(X_test) == 0:
            progress.progress(0)
            st.warning("筛选后测试集为空，请放宽条件。")
            return

        progress.progress(50, text=f"数据分割完成 — 测试集 {len(X_test)} 条")

        # 4. Load model & predict
        model = ProductionTimeModel()
        model.load(model_path)
        y_pred = model.predict(X_test)
        progress.progress(80, text="预测完成")

        # 5. Metrics (SMAPE: symmetric, immune to small-denominator inflation)
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mae = float(mean_absolute_error(y_test, y_pred))
        r2 = float(r2_score(y_test, y_pred)) if len(y_test) > 1 else 0.0
        denom = (np.abs(y_test.values) + np.abs(y_pred)) / 2.0
        smape_mask = denom > 0
        mape = float(np.mean(np.abs(y_test.values[smape_mask] - y_pred[smape_mask]) / denom[smape_mask]) * 100) if smape_mask.sum() else 0.0
        progress.progress(100, text="✅ 测试完成")

        # ---- 展示 ----
        _display_test_results(y_test.values, y_pred, meta_test, meta_cols,
                              rmse, mae, r2, mape, test_size, model_path, material_filter)

    except Exception as e:
        progress.progress(0, text="❌ 测试失败")
        st.error(f"模型测试失败: {e}")
        import traceback
        st.code(traceback.format_exc(), language="text")


def _run_model_predict_uploaded(uploaded_file, model_path: str, data_dir: str):
    """使用已训练模型对上传的 CSV 进行预测"""
    import importlib
    import src.data_processing.aps_data_loader as _ld_mod
    import src.data_processing.production_time_feature_engineer as _fe_mod
    import src.models.production_time_model as _md_mod
    importlib.reload(_ld_mod); importlib.reload(_fe_mod); importlib.reload(_md_mod)
    from src.data_processing.aps_data_loader import APSDataLoader
    from src.data_processing.production_time_feature_engineer import ProductionTimeFeatureEngineer
    from src.models.production_time_model import ProductionTimeModel

    progress = st.progress(0, text="读取上传文件...")
    try:
        uploaded_df = pd.read_csv(uploaded_file, encoding="utf-8")
        st.caption(f"上传数据: {len(uploaded_df)} 行, {len(uploaded_df.columns)} 列")
        progress.progress(10)

        # 用 APSDataLoader 加载 FG/Capacity/Shortage 主数据，把上传文件当 History
        loader = APSDataLoader(data_dir=data_dir)
        loader.load_all_files()
        loader.history_df = uploaded_df
        history_clean = loader.preprocess_history()
        df = loader.merge_with_fg_data(history_clean)
        df = loader.merge_with_capacity(df)
        df = loader.merge_with_shortage(df)
        df = loader._create_basic_features(df)
        progress.progress(30, text="数据合并完成")

        fe = ProductionTimeFeatureEngineer(lookback_days=90)
        df_featured = fe.transform(df)
        feature_cols = fe.get_feature_columns(df_featured)
        X_new = df_featured[feature_cols].copy()
        progress.progress(50, text="特征工程完成")

        # Load model & predict
        model = ProductionTimeModel()
        model.load(model_path)
        y_pred = model.predict(X_new)
        progress.progress(80, text="预测完成")

        # Build result
        meta_cols = [c for c in [
            'production_number', 'material', 'material_description',
            'order_quantity', 'planned_start_date', 'planned_finish_date',
        ] if c in df_featured.columns]
        result_df = df_featured[meta_cols].copy().reset_index(drop=True)
        result_df['predicted_days'] = y_pred

        # 如果上传数据有实际完成日期，计算对比
        has_actual = 'actual_production_days' in df_featured.columns and df_featured['actual_production_days'].notna().sum() > 0
        if has_actual:
            y_actual = df_featured['actual_production_days'].values
            result_df['actual_days'] = y_actual
            result_df['error'] = y_actual - y_pred
            result_df['abs_error'] = np.abs(result_df['error'])

            from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
            valid = ~np.isnan(y_actual)
            if valid.sum() > 1:
                rmse = float(np.sqrt(mean_squared_error(y_actual[valid], y_pred[valid])))
                mae = float(mean_absolute_error(y_actual[valid], y_pred[valid]))
                r2 = float(r2_score(y_actual[valid], y_pred[valid]))
                st.subheader("📊 上传数据预测 vs 实际")
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("RMSE", f"{rmse:.3f} 天")
                with c2: st.metric("MAE", f"{mae:.3f} 天")
                with c3: st.metric("R²", f"{r2:.4f}")
                _explain_metrics(rmse=rmse, mae=mae, r2=r2)
        else:
            st.subheader("📊 预测结果")
            st.info("上传数据无实际完成日期，仅输出预测值。")

        progress.progress(100, text="✅ 完成")
        st.dataframe(result_df, use_container_width=True, height=500)

        # Download
        csv_bytes = result_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ 下载预测结果 CSV", csv_bytes,
                           file_name="predictions_uploaded.csv", mime="text/csv")

    except Exception as e:
        progress.progress(0, text="❌ 失败")
        st.error(f"预测失败: {e}")
        import traceback
        st.code(traceback.format_exc(), language="text")


def _explain_metrics(rmse: float, mae: float, r2: float, mape: float = None,
                     cv_rmse: float = None, cv_r2: float = None):
    """用通俗语言解释模型指标，帮助非技术用户理解模型表现"""

    # ---- 评级逻辑 ----
    def _rate_rmse(v):
        if v <= 1.0: return "🟢 优秀", "预测平均偏差不到 1 天"
        if v <= 2.0: return "🟡 良好", "预测平均偏差在 1~2 天"
        if v <= 3.0: return "🟠 一般", "预测平均偏差在 2~3 天，建议优化"
        return "🔴 较差", "预测偏差较大，需要更多数据或调参"

    def _rate_r2(v):
        if v >= 0.80: return "🟢 优秀", "模型能解释 80%+ 的 TPT 变化"
        if v >= 0.60: return "🟡 良好", "模型能解释 60~80% 的变化"
        if v >= 0.40: return "🟠 一般", "模型只解释了不到一半的变化"
        return "🔴 较差", "模型解释力不足，需改进"

    def _rate_mape(v):
        if v <= 10: return "🟢 优秀", "对称误差率 ≤10%，非常可靠"
        if v <= 20: return "🟡 良好", "对称误差率在 10~20%"
        if v <= 30: return "🟠 一般", "对称误差率在 20~30%，参考使用"
        return "🔴 较差", "误差率 >30%，需谨慎参考"

    rmse_badge, rmse_desc = _rate_rmse(rmse)
    r2_badge, r2_desc = _rate_r2(r2)

    lines = [
        "| 指标 | 值 | 评级 | 通俗解释 |",
        "|:---|:---|:---|:---|",
        f"| **RMSE**（均方根误差） | **{rmse:.3f} 天** | {rmse_badge} | {rmse_desc}。越小越好，代表预测与实际的平均偏差 |",
        f"| **MAE**（平均绝对误差） | **{mae:.3f} 天** | — | 预测平均偏离实际 {mae:.1f} 天。比 RMSE 更直观，不受极端值影响 |",
        f"| **R²**（决定系数） | **{r2:.4f}** | {r2_badge} | {r2_desc}。范围 0~1，越接近 1 越好 |",
    ]

    if mape is not None:
        mape_badge, mape_desc = _rate_mape(mape)
        lines.append(
            f"| **SMAPE**（对称平均百分比误差） | **{mape:.1f}%** | {mape_badge} | {mape_desc}。对短周期订单不会虚高，比 MAPE 更可靠 |"
        )

    if cv_rmse is not None and cv_r2 is not None:
        lines.append(
            f"| **交叉验证 RMSE** | **{cv_rmse:.3f} 天** | — | 5 次不同划分的稳定性指标，与 Test RMSE 接近说明模型稳定 |"
        )
        lines.append(
            f"| **交叉验证 R²** | **{cv_r2:.4f}** | — | 多次验证的泛化能力，越接近 Test R² 越可靠 |"
        )

    # ---- 综合结论 ----
    good_count = sum([rmse <= 2.0, r2 >= 0.60, (mape or 0) <= 20 or mape is None])
    if good_count >= 2:
        conclusion = "✅ **综合评价：模型可用于生产参考。** 预测结果有一定可信度，可结合业务经验使用。"
    elif good_count >= 1:
        conclusion = "⚠️ **综合评价：模型基本可用，建议持续优化。** 部分指标符合预期，建议增加训练数据或调整参数。"
    else:
        conclusion = "❌ **综合评价：模型不够理想。** 建议检查数据质量、增加训练数据量、或调整超参数后重新训练。"

    lines.append("")
    lines.append(conclusion)

    st.markdown("**💡 指标解读：**")
    st.markdown("\n".join(lines))


def _display_test_results(y_actual, y_pred, meta_test, meta_cols,
                          rmse, mae, r2, mape, test_size, model_path, material_filter):
    """展示测试结果的图表和表格"""
    st.subheader("📊 测试结果")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("RMSE", f"{rmse:.3f} 天")
    with c2: st.metric("MAE", f"{mae:.3f} 天")
    with c3: st.metric("R²", f"{r2:.4f}")
    with c4: st.metric("MAPE", f"{mape:.1f}%")

    _explain_metrics(rmse=rmse, mae=mae, r2=r2, mape=mape)

    desc_parts = [f"测试集 {len(y_actual)} 条（尾部 {test_size:.0%}）"]
    if material_filter:
        desc_parts.append(f"物料筛选: {', '.join(material_filter[:5])}")
    desc_parts.append(f"模型: `{_Path(model_path).name}`")
    st.caption(" · ".join(desc_parts))

    errors = y_actual - y_pred
    pred_df = pd.DataFrame({
        **{col: meta_test[col].values for col in meta_cols},
        'actual': y_actual,
        'predicted': y_pred,
        'error': errors,
        'abs_error': np.abs(errors),
    })

    # Scatter + Error histogram
    col_sc, col_err = st.columns(2)
    with col_sc:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pred_df['actual'], y=pred_df['predicted'],
            mode='markers', marker=dict(size=5, opacity=0.5, color='#e67e22'),
            name='测试样本',
        ))
        max_v = max(pred_df['actual'].max(), pred_df['predicted'].max()) + 1
        fig.add_trace(go.Scatter(x=[0, max_v], y=[0, max_v],
                                 mode='lines', line=dict(dash='dash', color='red'),
                                 name='完美预测线'))
        fig.update_layout(title="实际 vs 预测", xaxis_title="实际天数",
                          yaxis_title="预测天数", height=400, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    with col_err:
        fig = go.Figure(go.Histogram(x=errors, nbinsx=40, marker_color='#1abc9c', opacity=0.8))
        fig.add_vline(x=0, line_dash="dash", line_color="red")
        fig.update_layout(title="误差分布", xaxis_title="误差 (天)",
                          yaxis_title="样本数", height=400, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    # Detailed table
    with st.expander("📋 预测明细（前 100 条）", expanded=False):
        st.dataframe(
            pred_df.head(100).style.format({
                'actual': '{:.1f}', 'predicted': '{:.1f}',
                'error': '{:.2f}', 'abs_error': '{:.2f}',
            }),
            use_container_width=True, height=400,
        )


# ======================================================================
# 工具函数: 向 Streamlit 的 Tornado 服务注入 /predictions/ 路由
# ======================================================================

@st.cache_resource(show_spinner=False)
def _mount_predictions_route() -> bool:
    """在 Streamlit 内置 Tornado 服务器上挂载 /predictions/ 静态文件路由。
    通过 gc 找到进程内唯一的 tornado.web.Application 实例，然后调用
    add_handlers() 在 catch-all (.*)  路由之前插入 /predictions/ 规则。
    """
    import gc
    import tornado.web
    import tornado.httpserver
    try:
        # 方式 1: 通过 HTTPServer 找 Application
        app = None
        for obj in gc.get_objects():
            if isinstance(obj, tornado.httpserver.HTTPServer):
                cb = getattr(obj, "request_callback", None)
                if isinstance(cb, tornado.web.Application):
                    app = cb
                    break
        # 方式 2: 直接找 Application（备用）
        if app is None:
            for obj in gc.get_objects():
                if type(obj) is tornado.web.Application:
                    app = obj
                    break
        if app is None:
            return False
        pred_path = str(_PRED_DIR.resolve())

        # 自定义目录浏览 handler
        class _PredictionsIndexHandler(tornado.web.RequestHandler):
            @staticmethod
            def _list_files():
                import os
                files = []
                for name in os.listdir(pred_path):
                    p = os.path.join(pred_path, name)
                    if os.path.isfile(p):
                        stat = os.stat(p)
                        files.append({
                            "name": name,
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                        })
                files.sort(key=lambda x: -x["mtime"])
                return files

            def _write_html(self):
                import html
                from datetime import datetime

                files = self._list_files()
                self.set_header("Content-Type", "text/html; charset=utf-8")
                self.write("<html><head><title>predictions/ 文件列表</title></head><body>")
                self.write("<h2>predictions/ 文件列表</h2><ul>")
                for f in files:
                    url = "/predictions/" + html.escape(f["name"])
                    self.write(
                        f"<li><a href='{url}'>{html.escape(f['name'])}</a> "
                        f"({f['size']/1024:.1f} KB, "
                        f"{datetime.fromtimestamp(f['mtime']).strftime('%Y-%m-%d %H:%M:%S')})</li>"
                    )
                self.write("</ul></body></html>")

            def _write_json(self):
                from datetime import datetime

                files = self._list_files()
                payload = {
                    "path": "/predictions/",
                    "count": len(files),
                    "files": [
                        {
                            "name": f["name"],
                            "size": f["size"],
                            "size_kb": round(f["size"] / 1024, 1),
                            "mtime": f["mtime"],
                            "modified_at": datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M:%S"),
                            "url": f"/predictions/{f['name']}",
                        }
                        for f in files
                    ],
                }
                self.set_header("Content-Type", "application/json; charset=utf-8")
                self.write(payload)

            def get(self, index_type=None):
                if index_type == "json":
                    self._write_json()
                    return
                self._write_html()

        # 支持 ?Content-Type=JSON 参数，将 CSV 文件转为 JSON 返回
        class _PredictionsFileHandler(tornado.web.StaticFileHandler):
            async def get(self, path, include_body=True):
                if self.get_argument("Content-Type", None) == "JSON":
                    import os, csv, json
                    file_path = os.path.join(pred_path, path)
                    if not os.path.isfile(file_path):
                        raise tornado.web.HTTPError(404, "File not found")
                    suffix = os.path.splitext(path)[1].lower()
                    if suffix == ".csv":
                        with open(file_path, "r", encoding="utf-8-sig") as f:
                            rows = list(csv.DictReader(f))
                        # StaticFileHandler.finish() 需要 absolute_path 来计算 ETag
                        self.absolute_path = file_path
                        self.set_header("Content-Type", "application/json; charset=utf-8")
                        self.finish(json.dumps(
                            {"filename": path, "count": len(rows), "data": rows},
                            ensure_ascii=False,
                        ))
                    else:
                        raise tornado.web.HTTPError(400, "JSON conversion only supported for CSV files")
                    return
                await super().get(path, include_body)

        app.add_handlers(r".*", [
            (r"/predictions/index\.(json|html)", _PredictionsIndexHandler),
            (r"/predictions/?", _PredictionsIndexHandler),
            (r"/predictions/(.*)", _PredictionsFileHandler, {"path": pred_path}),
        ])
        return True
    except Exception:
        return False


# ======================================================================
# 页面 4: 预测结果浏览
# ======================================================================

def show_predictions():
    """浏览并预览 predictions/ 目录中的所有预测结果文件"""
    st.header("📁 预测结果")
    st.markdown("浏览 `predictions/` 目录中保存的所有预测输出文件，支持预览内容及下载。")
    st.markdown("---")

    pred_dir = _PRED_DIR
    if not pred_dir.exists():
        st.warning("`predictions/` 目录不存在。")
        return

    all_files = sorted(pred_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    csv_files = [f for f in all_files if f.suffix.lower() == ".csv"]
    json_files = [f for f in all_files if f.suffix.lower() == ".json"]
    other_files = [f for f in all_files if f.suffix.lower() not in (".csv", ".json")]

    # ---- 汇总指标 ----
    col1, col2, col3 = st.columns(3)
    col1.metric("CSV 文件数", len(csv_files))
    col2.metric("JSON 文件数", len(json_files))
    col3.metric("其他文件数", len(other_files))

    st.markdown("---")

    # ---- 文件选择 ----
    file_options = [f.name for f in all_files]
    if not file_options:
        st.info("predictions/ 目录为空。")
        return

    selected_name = st.selectbox(
        "选择文件预览",
        file_options,
        help="文件按修改时间倒序排列",
    )
    selected_path = pred_dir / selected_name

    # ---- 文件元信息 ----
    stat = selected_path.stat()
    info_col1, info_col2 = st.columns(2)
    info_col1.caption(f"大小: {stat.st_size / 1024:.1f} KB")
    info_col2.caption(f"修改时间: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")

    # ---- 预览内容 ----
    suffix = selected_path.suffix.lower()
    try:
        if suffix == ".csv":
            df = pd.read_csv(selected_path)
            st.success(f"共 {len(df):,} 行 × {len(df.columns)} 列")

            # 筛选行数
            max_rows = st.slider("预览行数", 10, min(500, len(df)), min(50, len(df)), 10)
            st.dataframe(df.head(max_rows), use_container_width=True)

            # 下载
            st.download_button(
                label="⬇️ 下载此 CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=selected_name,
                mime="text/csv",
            )

        elif suffix == ".json":
            import json
            with open(selected_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            st.json(content)

            st.download_button(
                label="⬇️ 下载此 JSON",
                data=json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=selected_name,
                mime="application/json",
            )

        else:
            with open(selected_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read(2000)
            st.text(text)

    except Exception as e:
        st.error(f"无法读取文件：{e}")

    # ---- 全部文件列表 ----
    st.markdown("---")
    with st.expander("📋 全部文件列表", expanded=False):
        rows = [
            {
                "文件名": f.name,
                "类型": f.suffix.upper(),
                "大小 (KB)": round(f.stat().st_size / 1024, 1),
                "修改时间": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            }
            for f in all_files
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# 首次加载时挂载 /predictions/ 路由
_mount_predictions_route()

if __name__ == "__main__":
    main()
