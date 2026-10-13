"""Streamlit hosting adapter for the original, self-contained Wenshi frontend."""
from pathlib import Path
import base64
import json
import mimetypes
import re

import streamlit as st

ROOT = Path(__file__).parent / "dist"
st.set_page_config(page_title="纹拾 · 让纹样生长于日常", page_icon="🎨", layout="wide")


@st.cache_data
def bundled_page(api_url: str = "") -> str:
    page = (ROOT / "index.html").read_text(encoding="utf-8")
    page = re.sub(r'<link[^>]+href="([^"/]+\.css)"[^>]*>',
                  lambda m: '<style>' + (ROOT / m[1]).read_text(encoding="utf-8") + '</style>', page)
    page = re.sub(r'<script src="([^"/]+\.js)"></script>',
                  lambda m: '<script>' + (ROOT / m[1]).read_text(encoding="utf-8") + '</script>', page)
    for asset in (ROOT / "assets").iterdir():
        if asset.is_file():
            mime = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
            uri = 'data:' + mime + ';base64,' + base64.b64encode(asset.read_bytes()).decode('ascii')
            page = page.replace('assets/' + asset.name, uri)
    worker = json.dumps((ROOT / "extract-worker.js").read_text(encoding="utf-8"), ensure_ascii=True)
    page = page.replace("new Worker('extract-worker.js')", "new Worker(URL.createObjectURL(new Blob([" + worker + "], {type:'text/javascript'})))")
    # srcdoc has no standalone URL. Navigation remains inside the embedded page.
    page = page.replace("history.replaceState(null,'','#'+id);", "")
    if api_url:
        page = page.replace("<head>", "<head><script>window.WENSHI_API_URL=" + json.dumps(api_url) + ";</script>")
        page = page.replace("支持纯色背景的基础分离，复杂背景暂不支持。照片在当前设备处理，不上传。",
                            "提取时照片会发送至云服务器进行 AI 处理，不保存原图。建议先裁剪到纹样主体。")
        page = page.replace('id="extract-demo" disabled>提取纹样', 'id="extract-demo" disabled>AI 提取纹样')
    return page


# Match the original full-window layout rather than Streamlit's padded content
# column. Select by the stable accessible title of this single iframe.
st.html('''<style>
html, body, [data-testid="stAppViewContainer"] {background:#efe5d2;}
[data-testid="stHeader"], [data-testid="stToolbar"] {display:none;}
iframe[title="纹拾创作网站"] {
  position:fixed; inset:0; width:100vw !important;
  height:100dvh !important; border:0; z-index:100;
}
</style>''')
config_file = Path(__file__).parent / "cloud_config.json"
api_url = json.loads(config_file.read_text(encoding="utf-8")).get("api_url", "") if config_file.exists() else ""
st.iframe(bundled_page(api_url), height=900, alt="纹拾创作网站")
