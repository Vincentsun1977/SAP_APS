from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from streamlit_app.sidebar_theme import apply_sidebar_theme
from streamlit_app.page_views.testing_lab import show_testing_lab


apply_sidebar_theme()
show_testing_lab()
