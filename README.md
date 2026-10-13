# 纹拾 Pattern Finds

基于 Streamlit 的纹样采集与文创设计网站，保留原网页布局和交互。

## Streamlit Community Cloud 部署

- Repository: `normazzz271828-prog/Pattern-Finds`
- Branch: `main`
- Main file path: `streamlit_app.py`
- Python: `3.11`
- 建议网址前缀：`pattern-finds`，以平台可用性为准。

本地运行：`pip install -r requirements.txt` 后执行 `streamlit run streamlit_app.py`。

功能包括图片选择、纯色背景分离、纹样分类、书签/明信片/海报编辑和 SVG 导出。照片在访问者浏览器处理，不上传；复杂背景的 AI 分割尚未接入。刷新会清除当前操作。

`dist/` 保存网页和素材，Streamlit 入口将其打包为独立 HTML，不依赖其他网站。
