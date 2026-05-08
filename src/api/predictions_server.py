import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PREDICTIONS_DIR = BASE_DIR / "predictions"

app = FastAPI(title="Predictions File API", version="1.0.0")


def _safe_filename(filename: str) -> Path:
    """校验文件名安全性，防止路径遍历攻击。返回绝对路径，不存在时抛出 404。"""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = PREDICTIONS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    return file_path


def _build_index_json() -> dict:
    files = []
    for f in sorted(PREDICTIONS_DIR.iterdir()):
        if f.is_file():
            stat = f.stat()
            files.append(
                {
                    "name": f.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "type": f.suffix.lstrip(".") or "unknown",
                }
            )
    return {"files": files, "count": len(files), "generated_at": datetime.now().isoformat()}


def _build_index_html() -> str:
    rows = ""
    for f in sorted(PREDICTIONS_DIR.iterdir()):
        if f.is_file():
            stat = f.stat()
            size_kb = stat.st_size / 1024
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            rows += (
                f"<tr>"
                f"<td><a href='/predictions/{f.name}'>{f.name}</a></td>"
                f"<td>{size_kb:.1f} KB</td>"
                f"<td>{modified}</td>"
                f"</tr>\n"
            )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Predictions</title>
<style>
body{{font-family:monospace;padding:20px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ccc;padding:6px 12px;text-align:left}}
th{{background:#f5f5f5}}
a{{text-decoration:none;color:#0066cc}}
</style>
</head><body>
<h2>Predictions Directory</h2>
<p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
<table><thead><tr><th>Filename</th><th>Size</th><th>Modified</th></tr></thead>
<tbody>{rows}</tbody></table>
</body></html>"""


def _want_format(request: Request, format_param: Optional[str], target: str) -> bool:
    """判断是否希望返回指定格式（json / html / csv）。
    优先级：?format= 参数 > Accept 头。
    """
    if format_param:
        return format_param.lower() == target
    accept = request.headers.get("accept", "")
    mapping = {"json": "application/json", "html": "text/html", "csv": "text/csv"}
    return mapping.get(target, "") in accept


@app.get("/predictions")
def get_index(request: Request, format: Optional[str] = None):
    # 优先级：?format= > Accept 头 > 默认 HTML
    if _want_format(request, format, "json"):
        return JSONResponse(_build_index_json())
    return HTMLResponse(_build_index_html())


@app.get("/predictions/{filename}")
def get_file(request: Request, filename: str, format: Optional[str] = None):
    file_path = _safe_filename(filename)

    # JSON：?format=json 或 Accept: application/json
    if _want_format(request, format, "json"):
        if file_path.suffix.lower() != ".csv":
            raise HTTPException(status_code=400, detail="JSON conversion only supported for .csv files")
        df = pd.read_csv(file_path)
        # 使用 pandas to_json 序列化，NaN → null，避免标准 json 模块报错
        json_str = df.to_json(orient="records", force_ascii=False)
        return Response(content=json_str, media_type="application/json")

    # 返回原始文件内容
    mime_type, _ = mimetypes.guess_type(file_path.name)
    if mime_type is None:
        mime_type = "application/octet-stream"
    content = file_path.read_bytes()
    return Response(content=content, media_type=mime_type)
