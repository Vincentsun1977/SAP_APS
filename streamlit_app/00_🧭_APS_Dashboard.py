from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from streamlit_app.sidebar_theme import apply_sidebar_theme
from streamlit_app.aps_dashboard import main


apply_sidebar_theme(title="APS DASHBOARD")
main()
