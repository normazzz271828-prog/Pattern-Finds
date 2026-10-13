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
def bundled_page() -> str:
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
st.iframe(bundled_page(), height=900, alt="纹拾创作网站")
