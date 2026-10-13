# Streamlit 与阿里云接口

正式网页入口：https://patternfinds.streamlit.app/

Streamlit 从 cloud_config.json 读取公开 API 地址，将图片提取请求发送至阿里云 ECS。静态调试模式未配置接口时继续使用浏览器 Worker。照片仅在用户点击提取后发送，服务不写入上传文件。页面显示云端处理状态及失败提示。

当前接口使用完整 U²-Net ONNX 模型在 CPU 上执行真实主体分割。模型是通用显著主体检测模型，尚未针对传统纹样专门训练；密集重复纹样、同色细线和多个主体建议先裁剪，再检查透明结果。已保留透明度的 PNG 直接保留透明度；最长边处理为 1600 像素。上传限制 15 MB、2400 万像素，一次只处理一个请求，繁忙时提示重试。

ECS 使用 /opt/wenshi 下的独立 Python 运行时、虚拟环境和应用，以 wenshi 用户运行。API 仅监听 127.0.0.1:8510，由独立 cloudflared 进程提供 HTTPS 访问；没有修改已有 Nginx 站点或其他应用。服务名称：wenshi-api、wenshi-api-tunnel。

目前使用 Quick Tunnel 试用连接：没有可用的自有 API 域名或 Cloudflare 账号授权，因此尚未设置固定接口域名。隧道进程重启会生成新地址，需要同步 cloud_config.json；API 服务单独重启不会重启隧道。生产使用应迁移到固定 HTTPS 域名或命名隧道。浏览器直接调用公开接口，CORS 来源为正式 Streamlit 网站；上传有大小、像素、并发和频率限制。

cloud_config.json 不含凭据。后续模型提供商凭据仅放在服务器，不放入前端。本次接入未使用付费模型 API。后续更高质量模型仍需评估效果与资源成本。

参考：https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/

## AI 模型实测（2026-10-14）

对比完整 U²-Net 和轻量 U2NETP 后，当前使用完整版本，以单请求并发和 640 MB 内存硬上限控制资源。两种权重都已安装到 /opt/wenshi/models，MD5 验证一致，来源与 SHA256 记录在 backend/model-manifest.json；GitHub 不提交模型文件。

| 模型 | 合成纹样推理 | 官方照片推理 | 测试进程峰值 RSS | 合成纹样 IoU |
| --- | --- | --- | --- | --- |
| U2NETP | 1.60 秒 | 1.34 秒 | 358.8 MB | 0.9975 |
| U²-Net | 4.01 秒 | 8.18 秒 | 546.4 MB | 0.9992 |

这些只是单次受限 CPU 测试，IoU 来自人工生成的已知遮罩样例，不代表真实传统纹样数据集精度。官方样例是 U-2-Net 仓库提供的照片，仅用于本地/服务器 QA，不作为产品素材发布。主线程初始化时预热模型；健康接口成功后返回 ai_model=true、engine=u2net、device=cpu。

HTTPS API 已测试复杂纹理背景、官方照片、2400 万像素 JPG/PNG、空白图拒绝及透明图保留。端到端 HTTP 耗时包含网络传输，与纯推理耗时不同。大尺寸原图先缩小，再处理 EXIF，避免保留两份完整像素缓冲区。已保留透明通道的图像不再重跑分割，返回 preserved-alpha。

空白或无有效主体时返回 422；繁忙返回 503；不以基础算法静默替代失败的 AI 推理。AI 输出仍需用户检查，细线条可能漏检，背景可能残留。框架和运行时版本锁定在 backend/requirements.lock。

服务回滚备份保存在 /opt/wenshi/backups/before-ai，仅针对纹拾服务；隧道与其他应用无需重启。

模型来源：https://github.com/xuebinqin/U-2-Net
ONNX 发行来源：https://github.com/danielgatis/rembg
