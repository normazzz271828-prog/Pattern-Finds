# Streamlit 与阿里云接口

正式网页入口：https://patternfinds.streamlit.app/

Streamlit 从 cloud_config.json 读取公开 API 地址，将图片提取请求发送至阿里云 ECS。静态调试模式未配置接口时继续使用浏览器 Worker。照片仅在用户点击提取后发送，服务不写入上传文件。页面显示云端处理状态及失败提示。

当前接口是基础背景颜色分离，不包含 AI 模型，不提高复杂背景提取能力。已保留透明度的 PNG 直接保留透明度；最长边处理为 1600 像素。上传限制 15 MB、2400 万像素，一次只处理一个请求，繁忙时提示重试。

ECS 使用 /opt/wenshi 下的独立 Python 运行时、虚拟环境和应用，以 wenshi 用户运行。API 仅监听 127.0.0.1:8510，由独立 cloudflared 进程提供 HTTPS 访问；没有修改已有 Nginx 站点或其他应用。服务名称：wenshi-api、wenshi-api-tunnel。

目前使用 Quick Tunnel 试用连接：没有可用的自有 API 域名或 Cloudflare 账号授权，因此尚未设置固定接口域名。隧道进程重启会生成新地址，需要同步 cloud_config.json；API 服务单独重启不会重启隧道。生产使用应迁移到固定 HTTPS 域名或命名隧道。浏览器直接调用公开接口，CORS 来源为正式 Streamlit 网站；上传有大小、像素、并发和频率限制。

cloud_config.json 不含凭据。后续模型提供商凭据仅放在服务器，不放入前端。AI 模型效果、费用与性能需要另行验收。

参考：https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
