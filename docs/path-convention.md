# Path Convention

This project uses centralized path definitions in:

- `src/config/paths.py`

## Core rules

- Do not hardcode `data/...` or `models/...` strings in business code.
- Import paths from `src.config.paths` in Streamlit pages, scripts, and loaders.
- If directory layout changes, update `src/config/paths.py` only.

## Standard directories

- Raw data: `data/raw`
- Processed data: `data/processed`
- Sample data: `data/sample`
- Inference input: `data/inference_input`
- Inference output: `data/inference_output`
- Models: `models`
- Reports: `reports`

## Standard files and patterns

- APS processed training data: `APS_TRAINING_DATA_PATH`
- APS model pattern: `aps_xgb_model_*.json`
- Legacy model pattern: `xgb_model_*.json`
- Latest APS model helper: `get_latest_aps_model_path()`
- Latest legacy model helper: `get_latest_legacy_xgb_model_path()`

## Usage examples

```python
from src.config.paths import RAW_DATA_DIR, APS_TRAINING_DATA_PATH, get_latest_aps_model_path

df = pd.read_csv(APS_TRAINING_DATA_PATH)
model_path = get_latest_aps_model_path()
loader = APSDataLoader(data_dir=str(RAW_DATA_DIR))
```

