"""
SAP Production ML Workbench - 统一入口
集成数据管理、特征工程、模型训练、测试、评估和生产Dashboard
"""
import streamlit as st
import sys
sys.path.append('.')

from streamlit_app.sidebar_theme import apply_sidebar_theme


def _patch_plotly_chart_api():
    """
    兼容旧版 st.plotly_chart 参数，避免 Streamlit 1.50 的 kwargs deprecation warning。
    - width='stretch' -> use_container_width=True
    - 旧Plotly配置参数 -> 合并到 config={}
    """
    original_plotly_chart = st.plotly_chart

    if getattr(original_plotly_chart, "__name__", "") == "_plotly_chart_compat":
        return

    def _plotly_chart_compat(figure_or_data, *args, **kwargs):
        width = kwargs.pop("width", None)
        use_container_width = kwargs.pop("use_container_width", None)
        if use_container_width is None:
            use_container_width = (width == "stretch") if width is not None else True

        config = dict(kwargs.pop("config", {}) or {})
        deprecated_config_keys = [
            "displayModeBar",
            "scrollZoom",
            "editable",
            "showLink",
            "linkText",
            "toImageButtonOptions",
            "modeBarButtonsToRemove",
            "modeBarButtonsToAdd",
            "displaylogo",
        ]
        for key in deprecated_config_keys:
            if key in kwargs:
                config[key] = kwargs.pop(key)

        theme = kwargs.pop("theme", "streamlit")
        key = kwargs.pop("key", None)
        on_select = kwargs.pop("on_select", "ignore")
        selection_mode = kwargs.pop("selection_mode", ("points", "box", "lasso"))

        # 任何剩余未知参数都并入config，避免触发Streamlit kwargs弃用告警
        if kwargs:
            config.update(kwargs)

        return original_plotly_chart(
            figure_or_data,
            use_container_width=use_container_width,
            theme=theme,
            key=key,
            on_select=on_select,
            selection_mode=selection_mode,
            config=config or None,
        )

    _plotly_chart_compat.__name__ = "_plotly_chart_compat"
    st.plotly_chart = _plotly_chart_compat


_patch_plotly_chart_api()

# Page config - 必须在最前面
st.set_page_config(
    page_title="SAP Production ML Workbench",
    page_icon=":material/manufacturing:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    :root {
        --studio-bg: #f4f6fb;
        --studio-panel: #fbfcff;
        --studio-panel-alt: #eef2f9;
        --studio-border: #dce3f1;
        --studio-ink: #1f2a3a;
        --studio-subtle: #576478;
        --studio-muted: #7b8799;
        --studio-accent: #1f5fbf;
        --studio-accent-soft: #e5efff;
        --studio-shadow: 0 2px 10px rgba(31, 42, 58, 0.06);
    }
    .stApp {
        font-family: "Plus Jakarta Sans", "Manrope", "DM Sans", sans-serif;
        background: linear-gradient(180deg, #f7f9fd 0%, var(--studio-bg) 100%);
        color: var(--studio-ink);
    }
    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 2rem;
    }
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: var(--studio-ink);
        text-align: left;
        letter-spacing: -0.03em;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.98rem;
        color: var(--studio-subtle);
        text-align: left;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background: var(--studio-panel);
        padding: 1.5rem;
        border-radius: 12px;
        color: var(--studio-ink);
        border: 1px solid var(--studio-border);
        box-shadow: var(--studio-shadow);
    }
    .risk-high { background-color: #ffebee; border-left: 4px solid #d32f2f; padding: 10px; }
    .risk-medium { background-color: #fff3e0; border-left: 4px solid #ff9800; padding: 10px; }
    .risk-low { background-color: #e8f5e9; border-left: 4px solid #4caf50; padding: 10px; }
    section[data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.9);
        border-right: 1px solid var(--studio-border);
        backdrop-filter: blur(12px);
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.25rem;
        padding-left: 1.15rem;
        padding-right: 1.15rem;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
        width: 100%;
        justify-content: flex-start;
        min-height: 54px;
        border-radius: 10px;
        border: 1px solid transparent;
        background: transparent !important;
        color: var(--studio-ink);
        font-size: 0.97rem;
        font-weight: 600;
        letter-spacing: -0.01em;
        padding: 0.68rem 0.85rem;
        transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button p {
        display: flex;
        align-items: center;
        gap: 0.62rem;
        margin: 0;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button svg {
        width: 1.15rem;
        height: 1.15rem;
        flex-shrink: 0;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
        background: #eceff3 !important;
        border-color: #d6dce6 !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"],
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[data-testid="baseButton-primary"] {
        background: #3d434d !important;
        color: #ffffff !important;
        border-color: #3d434d !important;
        box-shadow: 0 3px 10px rgba(31, 42, 58, 0.2);
    }
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[kind="primary"]:hover,
    section[data-testid="stSidebar"] div[data-testid="stButton"] > button[data-testid="baseButton-primary"]:hover {
        background: #343941 !important;
        border-color: #343941 !important;
    }
    .workbench-subtitle {
        color: var(--studio-muted);
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 0.14em;
        margin-bottom: 0.35rem;
    }
    .workbench-title {
        color: var(--studio-ink);
        font-size: 1.14rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        margin-bottom: 1.1rem;
    }
    .workbench-status {
        margin-top: 0.45rem;
        padding: 1rem 1rem 0.9rem 1rem;
        border: 1px solid var(--studio-border);
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.82);
        color: var(--studio-subtle);
        font-size: 0.92rem;
        line-height: 1.9;
        box-shadow: var(--studio-shadow);
    }
    .workbench-nav-title {
        margin-top: 0.4rem;
        margin-bottom: 0.35rem;
        color: var(--studio-muted);
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.14em;
    }
    .status-row {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        flex: 0 0 8px;
    }
    .status-dot-ready {
        background: #16a34a;
    }
    .status-dot-pending {
        background: #a8b1bf;
    }
    .sidebar-settings-divider {
        margin-top: 0.95rem;
        margin-bottom: 0.75rem;
        border-top: 1px solid var(--studio-border);
    }
    .sidebar-settings-title {
        color: var(--studio-muted);
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.14em;
        margin-bottom: 0.45rem;
    }
    .studio-shell {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: rgba(255, 255, 255, 0.75);
        border: 1px solid var(--studio-border);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        box-shadow: var(--studio-shadow);
        margin-bottom: 1rem;
    }
    .studio-kicker {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        color: var(--studio-accent);
        background: var(--studio-accent-soft);
        border: 1px solid #d2e3fc;
        border-radius: 10px;
        padding: 0.3rem 0.72rem;
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 0.55rem;
    }
    .studio-title {
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        color: var(--studio-ink);
        margin: 0;
    }
    .studio-copy {
        margin-top: 0.2rem;
        color: var(--studio-subtle);
        font-size: 0.95rem;
    }
    .studio-badge {
        color: var(--studio-subtle);
        background: #fbfcff;
        border: 1px solid var(--studio-border);
        border-radius: 10px;
        padding: 0.45rem 0.75rem;
        font-size: 0.82rem;
        font-weight: 600;
    }
    div[data-testid="stMetric"] {
        background: var(--studio-panel);
        border: 1px solid var(--studio-border);
        border-radius: 12px;
        padding: 1rem 1rem 0.9rem 1rem;
        box-shadow: var(--studio-shadow);
    }
    div[data-testid="stMetric"] label {
        color: var(--studio-subtle);
    }
    div[data-baseweb="tab-list"] {
        gap: 0.35rem;
        background: transparent;
    }
    button[data-baseweb="tab"] {
        border-radius: 10px;
        background: #fbfcff;
        border: 1px solid var(--studio-border);
        color: var(--studio-subtle);
        padding: 0.5rem 0.9rem;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: var(--studio-accent-soft);
        border-color: #d2e3fc;
        color: var(--studio-accent);
    }
    .stButton > button, .stDownloadButton > button {
        border-radius: 10px;
        border: 1px solid #c7d7fe;
        background: var(--studio-accent-soft);
        color: var(--studio-accent);
        font-weight: 600;
        padding: 0.55rem 1rem;
    }
    .stButton > button[kind="primary"] {
        background: var(--studio-accent);
        color: #fff;
        border-color: var(--studio-accent);
    }
    .stTextInput input, .stNumberInput input, .stDateInput input, .stSelectbox [data-baseweb="select"] > div,
    .stMultiSelect [data-baseweb="select"] > div, .stTextArea textarea {
        border-radius: 10px !important;
        border-color: var(--studio-border) !important;
        background: #fbfcff !important;
    }
    .stDataFrame, .stPlotlyChart, .stAlert, .stExpander, div[data-testid="stFileUploader"] {
        background: var(--studio-panel);
        border: 1px solid var(--studio-border);
        border-radius: 12px;
        box-shadow: var(--studio-shadow);
    }
    div[data-testid="stFileUploader"] {
        padding: 0.5rem 0.75rem;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--studio-panel);
        border: 1px solid var(--studio-border) !important;
        border-radius: 12px;
        box-shadow: var(--studio-shadow);
        padding: 0.65rem 0.8rem;
        margin-bottom: 0.95rem;
    }
    .section-card-title {
        font-size: 1.08rem;
        font-weight: 700;
        color: var(--studio-ink);
        letter-spacing: -0.02em;
        margin-bottom: 0.2rem;
    }
    .section-card-subtitle {
        font-size: 0.9rem;
        color: var(--studio-subtle);
        margin-bottom: 0.8rem;
    }
    .page-header-shell {
        background: #f8faff;
        border: 1px solid var(--studio-border);
        border-radius: 12px;
        padding: 1.2rem 1.35rem;
        margin-bottom: 1.05rem;
        box-shadow: var(--studio-shadow);
    }
    .page-header-eyebrow {
        display: inline-flex;
        align-items: center;
        color: var(--studio-accent);
        background: var(--studio-accent-soft);
        border: 1px solid #d2e3fc;
        border-radius: 10px;
        padding: 0.28rem 0.68rem;
        font-size: 0.78rem;
        font-weight: 600;
        margin-bottom: 0.65rem;
    }
    .page-header-title {
        color: var(--studio-ink);
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.04em;
        line-height: 1.05;
    }
    .page-header-subtitle {
        color: var(--studio-subtle);
        font-size: 0.98rem;
        margin-top: 0.35rem;
    }
</style>
""", unsafe_allow_html=True)


def main():
    apply_sidebar_theme(title="Workspace", subtitle="Machine Learning")

    nav_items = [
        ("production_dashboard", ":material/dashboard:  Apps Dashboard"),
        ("data_manager", ":material/folder_open:  Data Manager"),
        ("feature_studio", ":material/auto_awesome:  Feature Studio"),
        ("training_console", ":material/model_training:  Training Console"),
        ("testing_lab", ":material/science:  Testing Lab"),
        ("evaluation_center", ":material/monitoring:  Evaluation Center"),
        ("trend_analysis", ":material/query_stats:  Production Dashboard"),
    ]

    if "active_page" not in st.session_state:
        st.session_state.active_page = "production_dashboard"

    for page_key, label in nav_items:
        if st.sidebar.button(
            label,
            key=f"nav_{page_key}",
            type="primary" if st.session_state.active_page == page_key else "secondary",
            width="stretch",
        ):
            st.session_state.active_page = page_key
            st.rerun()

    # Pipeline状态指示
    data_ready = st.session_state.get('data_loaded', False)
    features_ready = st.session_state.get('features_ready', False)
    model_ready = st.session_state.get('model_trained', False)

    st.sidebar.markdown('<div class="workbench-subtitle">PIPELINE STATUS</div>', unsafe_allow_html=True)

    st.sidebar.markdown(
        f"""
        <div class="workbench-status">
            <div class="status-row"><span class="status-dot {'status-dot-ready' if data_ready else 'status-dot-pending'}"></span><span>数据已加载</span></div>
            <div class="status-row"><span class="status-dot {'status-dot-ready' if features_ready else 'status-dot-pending'}"></span><span>特征已生成</span></div>
            <div class="status-row"><span class="status-dot {'status-dot-ready' if model_ready else 'status-dot-pending'}"></span><span>模型已训练</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown('<div class="sidebar-settings-divider"></div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="sidebar-settings-title">SETTINGS</div>', unsafe_allow_html=True)
    st.sidebar.text_input("File Path", key="settings_file_path", placeholder="e.g. data/raw")
    st.sidebar.text_input("SAP", key="settings_sap", placeholder="e.g. SAP ECC / S4")

    # 页面路由
    page_key = st.session_state.active_page

    if page_key == "data_manager":
        from streamlit_app.page_views.data_manager import show_data_manager
        show_data_manager()
    elif page_key == "feature_studio":
        from streamlit_app.page_views.feature_studio import show_feature_studio
        show_feature_studio()
    elif page_key == "training_console":
        from streamlit_app.page_views.training_console import show_training_console
        show_training_console()
    elif page_key == "testing_lab":
        from streamlit_app.page_views.testing_lab import show_testing_lab
        show_testing_lab()
    elif page_key == "evaluation_center":
        from streamlit_app.page_views.evaluation_center import show_evaluation_center
        show_evaluation_center()
    elif page_key == "production_dashboard":
        from streamlit_app.page_views.production_dashboard import show_production_dashboard
        show_production_dashboard()
    elif page_key == "realtime_prediction":
        from streamlit_app.page_views.production_dashboard import show_realtime_prediction
        show_realtime_prediction()
    elif page_key == "risk_materials":
        from streamlit_app.page_views.production_dashboard import show_risk_materials
        show_risk_materials()
    elif page_key == "trend_analysis":
        from streamlit_app.page_views.production_dashboard import show_trends
        show_trends()


if __name__ == "__main__":
    main()
