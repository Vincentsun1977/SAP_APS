"""Centralized filesystem paths for the project."""

from pathlib import Path
from typing import List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
SAMPLE_DATA_DIR = DATA_DIR / "sample"
INFERENCE_INPUT_DIR = DATA_DIR / "inference_input"
INFERENCE_OUTPUT_DIR = DATA_DIR / "inference_output"

MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

APS_TRAINING_DATA_PATH = PROCESSED_DATA_DIR / "aps_training_data_full.csv"
APS_MODEL_PATTERN = "aps_xgb_model_*.json"
APS_LATEST_MODEL_PATH = MODELS_DIR / "aps_xgb_model_latest.json"
LEGACY_XGB_MODEL_PATTERN = "xgb_model_*.json"
SAMPLE_PRODUCTION_ORDERS_PATH = SAMPLE_DATA_DIR / "production_orders.csv"


def get_aps_model_paths() -> List[Path]:
    """Return APS model paths sorted lexicographically."""
    return sorted(MODELS_DIR.glob(APS_MODEL_PATTERN))


def get_aps_model_paths_str() -> List[str]:
    """Return APS model paths as strings for UI controls."""
    return [str(p) for p in get_aps_model_paths()]


def get_latest_aps_model_path() -> Optional[Path]:
    """Return latest APS model path if available."""
    model_paths = get_aps_model_paths()
    return model_paths[-1] if model_paths else None


def get_legacy_xgb_model_paths() -> List[Path]:
    """Return legacy xgb model paths sorted lexicographically."""
    return sorted(MODELS_DIR.glob(LEGACY_XGB_MODEL_PATTERN))


def get_latest_legacy_xgb_model_path() -> Optional[Path]:
    """Return latest legacy xgb model path if available."""
    model_paths = get_legacy_xgb_model_paths()
    return model_paths[-1] if model_paths else None
