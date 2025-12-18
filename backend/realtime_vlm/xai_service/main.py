from __future__ import annotations

import asyncio
import base64
import io
import os
from typing import List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image

from ai_client import ai_client

app = FastAPI(title="XAI Attribution Service")


class XAIRequest(BaseModel):
    image_base64: str
    frame_number: int
    timestamp: str
    scene_description: Optional[str] = None
    detected_hazards: Optional[List[str]] = None
    grid_size: Optional[int] = None


class PatchAttribution(BaseModel):
    row: int
    col: int
    score: float
    summary: str


class XAIResponse(BaseModel):
    frame_number: int
    timestamp: str
    grid_size: int
    cells: List[PatchAttribution]
    max_score: float
    heatmap_image_base64: str
    explanation: str


GRID_SIZE = 8
PATCH_CONCURRENCY_LIMIT = max(1, int(os.getenv("XAI_MAX_CONCURRENCY", "6")))
_PATCH_SEMAPHORE: Optional[asyncio.Semaphore] = None


def _get_patch_semaphore() -> asyncio.Semaphore:
    global _PATCH_SEMAPHORE
    if _PATCH_SEMAPHORE is None:
        _PATCH_SEMAPHORE = asyncio.Semaphore(PATCH_CONCURRENCY_LIMIT)
    return _PATCH_SEMAPHORE


async def _score_patch_with_limit(
    patch_base64: str,
    row: int,
    col: int,
    grid_size: int,
    scene_context: str,
) -> dict:
    semaphore = _get_patch_semaphore()
    async with semaphore:
        return await ai_client.score_patch(
            patch_base64,
            row=row,
            col=col,
            grid_size=grid_size,
            scene_context=scene_context,
        )


def _strip_data_prefix(image_base64: str) -> str:
    if image_base64.startswith("data:"):
        try:
            return image_base64.split(",", 1)[1]
        except IndexError:
            return image_base64
    return image_base64


def _decode_image(image_base64: str) -> Image.Image:
    try:
        cleaned = _strip_data_prefix(image_base64)
        binary = base64.b64decode(cleaned)
        return Image.open(io.BytesIO(binary)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {exc}") from exc


def _encode_image(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    payload = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{payload}"


def _apply_colormap_gray_to_rgb(gray: np.ndarray) -> np.ndarray:
    """Map a 2D float array in [0,1] to an RGB uint8 image using a simple jet-like colormap."""
    g = np.clip(gray, 0.0, 1.0)
    # Define color stops for a jet-like map
    c0 = np.array([0, 0, 128], dtype=np.float32) / 255.0
    c1 = np.array([0, 0, 255], dtype=np.float32) / 255.0
    c2 = np.array([0, 255, 255], dtype=np.float32) / 255.0
    c3 = np.array([255, 255, 0], dtype=np.float32) / 255.0
    c4 = np.array([128, 0, 0], dtype=np.float32) / 255.0

    out = np.zeros((g.shape[0], g.shape[1], 3), dtype=np.float32)
    # piecewise interpolation
    out[g <= 0.25] = ((g[g <= 0.25, None] / 0.25) * (c1 - c0) + c0)
    mask = (g > 0.25) & (g <= 0.5)
    out[mask] = (((g[mask, None] - 0.25) / 0.25) * (c2 - c1) + c1)
    mask = (g > 0.5) & (g <= 0.75)
    out[mask] = (((g[mask, None] - 0.5) / 0.25) * (c3 - c2) + c2)
    mask = g > 0.75
    out[mask] = (((g[mask, None] - 0.75) / 0.25) * (c4 - c3) + c3)
    return (np.clip(out, 0.0, 1.0) * 255.0).astype(np.uint8)


def _blend_heatmap(image: Image.Image, importance: np.ndarray) -> str:
    # importance: grid_h x grid_w values in [0,1]
    grid_h, grid_w = importance.shape
    width, height = image.size

    # Normalize and convert to uint8 grayscale
    if importance.max() > 0:
        heat = importance / float(importance.max())
    else:
        heat = importance

    heat_uint8 = (np.clip(heat, 0.0, 1.0) * 255.0).astype(np.uint8)
    heat_img = Image.fromarray(heat_uint8, mode="L")

    # Upscale to image size with bicubic interpolation
    heat_up = heat_img.resize((width, height), resample=Image.BICUBIC)

    # Smooth with GaussianBlur
    try:
        from PIL import ImageFilter

        heat_up = heat_up.filter(ImageFilter.GaussianBlur(radius=5))
    except Exception:
        pass

    heat_arr = np.array(heat_up).astype("float32") / 255.0

    # Slight floor to suppress very low activations
    heat_arr = np.clip(heat_arr - 0.05, 0.0, 1.0)

    # Apply colormap
    colored = _apply_colormap_gray_to_rgb(heat_arr)

    # Create RGBA overlay with alpha channel based on heat intensity
    alpha = (heat_arr * 220).astype(np.uint8)
    rgba = np.dstack([colored, alpha])
    overlay = Image.fromarray(rgba, mode="RGBA")

    base = image.convert("RGBA")
    combined = Image.alpha_composite(base, overlay).convert("RGB")
    return _encode_image(combined)


@app.on_event("startup")
async def startup_event() -> None:
    _get_patch_semaphore()
    print(
        f"XAI attribution service ready (grid={GRID_SIZE}x{GRID_SIZE}, max concurrency={PATCH_CONCURRENCY_LIMIT})"
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "xai"}


@app.post("/analyze", response_model=XAIResponse)
async def analyze(request: XAIRequest) -> XAIResponse:
    original_image = _decode_image(request.image_base64)
    width, height = original_image.size

    grid_size = GRID_SIZE
    cell_width = max(1, width // grid_size)
    cell_height = max(1, height // grid_size)

    importance = np.zeros((grid_size, grid_size), dtype=np.float32)
    cells: List[PatchAttribution] = []
    scene_context = request.scene_description or ""

    task_handles = []
    for row in range(grid_size):
        for col in range(grid_size):
            x1 = min(width - 1, col * cell_width)
            y1 = min(height - 1, row * cell_height)
            if col == grid_size - 1:
                x2 = width
            else:
                x2 = min(width, x1 + cell_width)
            if row == grid_size - 1:
                y2 = height
            else:
                y2 = min(height, y1 + cell_height)
            if x2 <= x1:
                x2 = min(width, x1 + 1)
            if y2 <= y1:
                y2 = min(height, y1 + 1)

            patch = original_image.crop((x1, y1, x2, y2))
            patch_b64 = _encode_image(patch)
            task = asyncio.create_task(
                _score_patch_with_limit(
                    patch_b64,
                    row=row,
                    col=col,
                    grid_size=grid_size,
                    scene_context=scene_context,
                )
            )
            task_handles.append(((row, col), task))

    task_results = await asyncio.gather(
        *(task for _, task in task_handles), return_exceptions=True
    )

    for ((row, col), _), result in zip(task_handles, task_results):
        if isinstance(result, Exception):
            score = 0.0
            summary = f"Scoring failed: {result}"[:180]
        else:
            score = float(result.get("score", 0.0))
            summary = str(result.get("summary", ""))
        importance[row, col] = score
        cells.append(PatchAttribution(row=row, col=col, score=score, summary=summary))

    max_score = max((cell.score for cell in cells), default=0.0)
    explanation_entries = sorted(cells, key=lambda c: c.score, reverse=True)[:3]
    explanation = "; ".join(
        f"({cell.row + 1},{cell.col + 1}) score={cell.score:.2f} {cell.summary}"
        for cell in explanation_entries
    )
    overlay_b64 = _blend_heatmap(original_image, importance)

    return XAIResponse(
        frame_number=request.frame_number,
        timestamp=request.timestamp,
        grid_size=grid_size,
        cells=cells,
        max_score=max_score,
        heatmap_image_base64=overlay_b64,
        explanation=explanation,
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await ai_client.close()
