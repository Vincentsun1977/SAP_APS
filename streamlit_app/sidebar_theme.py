import streamlit as st


def apply_sidebar_theme(title: str = "Navigation", subtitle: str = "Machine Learning") -> None:
    st.markdown(
        f"""
        <style>
            section[data-testid="stSidebar"] {{
                background: rgba(255, 255, 255, 0.92);
                border-right: 1px solid #e3e8f4;
                backdrop-filter: blur(12px);
            }}

            section[data-testid="stSidebar"] .block-container {{
                padding-top: 1.35rem;
                padding-left: 1.1rem;
                padding-right: 1.1rem;
            }}

            [data-testid="stSidebarNav"] {{
                margin-top: 0.4rem;
            }}

            [data-testid="stSidebarNav"] > div:first-child {{
                display: none;
            }}

            [data-testid="stSidebarNav"] ul {{
                gap: 0.35rem;
            }}

            [data-testid="stSidebarNav"] li {{
                margin: 0;
            }}

            [data-testid="stSidebarNav"] a {{
                min-height: 56px;
                padding: 0.92rem 1rem;
                border-radius: 0;
                color: #0f172a;
                font-size: 1rem;
                font-weight: 600;
                letter-spacing: -0.02em;
                transition: background-color 0.18s ease, color 0.18s ease;
            }}

            [data-testid="stSidebarNav"] a:hover {{
                background: #f5f7fb;
                color: #111827;
            }}

            [data-testid="stSidebarNav"] a[aria-current="page"] {{
                background: #4338ca;
                color: #ffffff;
                border-radius: 0;
                box-shadow: 0 12px 24px rgba(67, 56, 202, 0.22);
            }}

            [data-testid="stSidebarNav"] a span {{
                color: inherit;
            }}

            [data-testid="stSidebarNav"] a svg {{
                width: 1.15rem;
                height: 1.15rem;
            }}

            .sidebar-category-label {{
                font-size: 1.12rem;
                font-weight: 700;
                letter-spacing: -0.02em;
                color: #202124;
                margin: 0.1rem 0 1.15rem 0;
            }}

            .sidebar-category-subtitle {{
                font-size: 0.74rem;
                font-weight: 700;
                letter-spacing: 0.14em;
                color: #0b57d0;
                margin-bottom: 0.38rem;
            }}

            .sidebar-title-shell {{
                background: linear-gradient(180deg, rgba(232, 240, 254, 0.72), rgba(255, 255, 255, 0.82));
                border: 1px solid #d2e3fc;
                border-radius: 20px;
                padding: 0.9rem 0.95rem;
                margin-bottom: 1rem;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        f"""
        <div class="sidebar-title-shell">
            <div class="sidebar-category-subtitle">{subtitle}</div>
            <div class="sidebar-category-label">{title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
