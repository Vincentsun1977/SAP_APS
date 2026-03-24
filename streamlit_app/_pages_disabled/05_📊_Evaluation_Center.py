from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from streamlit_app.sidebar_theme import apply_sidebar_theme
from streamlit_app.page_views.evaluation_center import show_evaluation_center


apply_sidebar_theme()
show_evaluation_center()
