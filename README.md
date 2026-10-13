# 纹拾 Pattern Finds

基于 Streamlit 的纹样采集与文创设计网站，保留原网页布局和交互。

## Streamlit Community Cloud 部署

- Repository: `normazzz271828-prog/Pattern-Finds`
- Branch: `main`
- Main file path: `streamlit_app.py`
- Python: `3.11`
- 建议网址前缀：`pattern-finds`，以平台可用性为准。

本地运行：`pip install -r requirements.txt` 后执行 `streamlit run streamlit_app.py`。

功能包括图片选择、纯色背景分离、纹样分类、书签/明信片/海报编辑和 SVG 导出。配置 cloud_config.json 后，照片在点击提取时发送到阿里云 ECS，服务器在内存中处理，不保存原图；独立静态预览使用浏览器处理。复杂背景的 AI 分割尚未接入。刷新会清除当前操作。

`dist/` 保存网页和素材，Streamlit 入口将其打包为独立 HTML，不依赖其他网站。

当前正式入口：https://patternfinds.streamlit.app/

云端接入详情、临时 HTTPS 隧道的限制及部署文件见 [SERVER.md](SERVER.md)。
