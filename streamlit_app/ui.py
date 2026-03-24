import streamlit as st
from contextlib import contextmanager


def render_page_header(title: str, subtitle: str, eyebrow: str = "Workspace") -> None:
    st.markdown(
        f"""
        <div class="page-header-shell">
            <div class="page-header-eyebrow">{eyebrow}</div>
            <div class="page-header-title">{title}</div>
            <div class="page-header-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def render_section_card(title: str = "", subtitle: str = ""):
    with st.container(border=True):
        if title:
            st.markdown(f'<div class="section-card-title">{title}</div>', unsafe_allow_html=True)
        if subtitle:
            st.markdown(f'<div class="section-card-subtitle">{subtitle}</div>', unsafe_allow_html=True)
        yield
