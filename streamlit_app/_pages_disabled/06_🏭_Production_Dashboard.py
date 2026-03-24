from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from streamlit_app.sidebar_theme import apply_sidebar_theme
from streamlit_app.page_views.production_dashboard import (
    show_production_dashboard,
    show_realtime_prediction,
    show_risk_materials,
    show_trends,
)


PAGE_ROUTER = {
    "🏭 Production Dashboard": show_production_dashboard,
    "🔮 Realtime Prediction": show_realtime_prediction,
    "⚠️ Risk Materials": show_risk_materials,
    "📈 Trend Analysis": show_trends,
}


apply_sidebar_theme()
show_production_dashboard()
