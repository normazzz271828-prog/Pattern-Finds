"""Bounded, in-memory background separation service for the ECS pilot."""
import asyncio
from contextlib import asynccontextmanager
from collections import OrderedDict
from io import BytesIO
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, UnidentifiedImageError
import numpy as np
from starlette.concurrency import run_in_threadpool
from backend.segmentation import foreground_mask, warmup, MODEL_NAME

@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(warmup)
    yield

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
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
            # Reduce before EXIF's copy to avoid two full-resolution buffers.
            source.draft("RGB", (1600, 1600))
            source.thumbnail((1600, 1600))
            image = ImageOps.exif_transpose(source)
            pixels = np.array(image.convert("RGBA"))
        preserved = np.mean(pixels[:, :, 3] < 240) > 0.01
        if not preserved:
            mask = np.asarray(foreground_mask(Image.fromarray(pixels)), dtype=np.float32) / 255
            pixels[:, :, 3] = np.rint(pixels[:, :, 3]*mask).astype(np.uint8)
        output = BytesIO()
        Image.fromarray(pixels).save(output, format="PNG")
        return output.getvalue(), "preserved-alpha" if preserved else "ai-" + MODEL_NAME
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("图片无法读取或尺寸过大，请更换图片。") from error


@app.get("/health")
def health():
    return {"status": "ok", "service": "wenshi", "engine": MODEL_NAME, "ai_model": True, "device": "cpu"}


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
