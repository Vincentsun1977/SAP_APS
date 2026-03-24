from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from streamlit_app.sidebar_theme import apply_sidebar_theme
from streamlit_app.page_views.training_console import show_training_console


apply_sidebar_theme()
show_training_console()
