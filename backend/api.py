"""Bounded, in-memory background separation service for the ECS pilot."""
import asyncio
from collections import OrderedDict
from io import BytesIO
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, UnidentifiedImageError
import numpy as np
from starlette.concurrency import run_in_threadpool

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["https://patternfinds.streamlit.app"],
                   allow_methods=["POST", "GET"], allow_headers=["Content-Type"],
                   expose_headers=["X-Wenshi-Method"])
MAX_BYTES = 15 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 24_000_000
slots = asyncio.Semaphore(1)
recent = OrderedDict()


def separate(raw):
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("请选择 JPG、PNG 或 WebP 图片。")
            if source.width * source.height > 24_000_000:
                raise ValueError("图片尺寸超过 2400 万像素。")
            image = ImageOps.exif_transpose(source)
            image.thumbnail((1600, 1600))
            pixels = np.array(image.convert("RGBA"))
        preserved = np.mean(pixels[:, :, 3] < 240) > 0.01
        if not preserved:
            rgb = pixels[:, :, :3].astype(np.float32)
            edge = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
            bg = np.median(edge, axis=0)
            if np.mean(np.linalg.norm(edge - bg, axis=1) < 45) < .7:
                raise ValueError("背景较复杂，请换用纯色背景照片，或先裁剪纹样。")
            alpha = np.clip((np.linalg.norm(rgb-bg, axis=2)-25)/35, 0, 1)
            pixels[:, :, 3] = np.rint(pixels[:, :, 3]*alpha).astype(np.uint8)
            if np.mean(pixels[:, :, 3] > 128) < .002 or np.mean(pixels[:, :, 3] < 20) < .01:
                raise ValueError("没有找到清晰的纹样与背景，请更换对比更明显的照片。")
        output = BytesIO()
        Image.fromarray(pixels).save(output, format="PNG")
        return output.getvalue(), "preserved-alpha" if preserved else "basic-color-separation"
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("图片无法读取或尺寸过大，请更换图片。") from error


@app.get("/health")
def health():
    return {"status": "ok", "service": "wenshi", "engine": "basic-color-separation", "ai_model": False}


@app.post("/extract")
async def extract(request: Request):
    # Direct traffic only arrives from the loopback tunnel. Browser callers get
    # the same allowlist as the CORS policy; no upload is written to disk.
    origin = request.headers.get("origin")
    if origin and origin != "https://patternfinds.streamlit.app":
        raise HTTPException(403, "不允许的网页来源。")
    if request.headers.get("content-type", "").split(";")[0] not in {"image/png", "image/jpeg", "image/webp"}:
        raise HTTPException(415, "请选择 JPG、PNG 或 WebP 图片。")
    client = request.headers.get("cf-connecting-ip") or request.client.host
    now = time.monotonic()
    record = recent.get(client, [])
    record = [stamp for stamp in record if now-stamp < 60]
    if len(record) >= 10:
        raise HTTPException(429, "请求较多，请稍后重试。")
    recent[client] = record + [now]
    recent.move_to_end(client)
    while len(recent) > 2000:
        recent.popitem(last=False)
    try:
        await asyncio.wait_for(slots.acquire(), timeout=.1)
    except asyncio.TimeoutError:
        raise HTTPException(503, "服务器正在处理其他图片，请稍后重试。")
    try:
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > MAX_BYTES:
                raise HTTPException(413, "请选择 15 MB 以内的图片。")
        try:
            result, method = await run_in_threadpool(separate, bytes(chunks))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return Response(result, media_type="image/png", headers={
            "X-Wenshi-Method": method, "Cache-Control": "no-store"})
    finally:
        slots.release()
