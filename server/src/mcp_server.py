from __future__ import annotations

import base64
import os
import tempfile
from io import BytesIO
from typing import Optional

from PIL import Image as PILImage

from fastmcp import FastMCP
from fastmcp.utilities.types import Image

from .bridge_client import BridgeClient, BridgeError

mcp = FastMCP(
    "konva-canvas",
    instructions=(
        "A 2D canvas tool powered by Konva.js. "
        "Workflow: (1) create_canvas, (2) batch_design to add layers/shapes in bulk, "
        "(3) preview_canvas to inspect — fix issues with another batch_design call, "
        "(4) export_canvas when done. "
        "All IDs returned by tools must be passed into subsequent calls."
    ),
)

_bridge: BridgeClient | None = None

_PREVIEW_MAX_DIM = 800  # longest edge in pixels; keeps token cost low for VLMs

def _get_bridge() -> BridgeClient:
    if _bridge is None:
        raise RuntimeError("Bridge not initialized")
    return _bridge


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


_SKIP_CAMEL = {
    "canvas_id", "layer_id", "shape_id", "group_id", "shape_type",
    "shape_ids", "operation", "axis", "format", "pixel_ratio", "name", "file_path",
}
# Keys whose camelCase conversion doesn't follow the standard pattern
_PARAM_ALIASES: dict[str, str] = {
    "clock_wise": "clockwise",
}


def _camel_params(d: dict) -> dict:
    result = {}
    for k, v in d.items():
        if k in _PARAM_ALIASES:
            result[_PARAM_ALIASES[k]] = v
        elif k in _SKIP_CAMEL:
            result[k] = v
        else:
            result[_to_camel(k)] = v
    return result


async def _call(action: str, **kwargs) -> dict:
    params = _camel_params(_clean(kwargs))
    try:
        return await _get_bridge().execute(action, params)
    except BridgeError as e:
        return {"error": e.code, "message": str(e)}


@mcp.tool()
async def load_font(
    file_path: str,
    family: str,
    style: Optional[str] = None,
    weight: Optional[str] = None,
) -> dict:
    """Register a custom font file (.ttf, .otf, .woff) so it can be used in text shapes.

    Must be called BEFORE creating any text shapes that use this font family.
    Fonts are registered globally and persist for the lifetime of the bridge process.

    Args:
        file_path: Absolute path to the font file on disk (.ttf, .otf, or .woff).
        family: The font family name to register (e.g. "TT Supermolot Neue").
        style: Optional CSS font-style value (e.g. "normal", "italic"). Defaults to "normal".
        weight: Optional CSS font-weight value (e.g. "normal", "bold"). Defaults to "normal".
    """
    return await _call("load_font", file_path=file_path, family=family, style=style, weight=weight)


@mcp.tool()
async def create_canvas(width: int, height: int, background: Optional[str] = None) -> dict:
    """Create a new Konva canvas (Stage + default Layer). Returns canvas_id and layer_id.

    Args:
        width: Canvas width in pixels.
        height: Canvas height in pixels.
        background: Optional CSS color for the background (e.g. "#ffffff").
    """
    return await _call("create_canvas", width=width, height=height, background=background)


@mcp.tool()
async def image_info(file_path: str) -> dict:
    """Return metadata about an image file without placing it on a canvas.

    Returns {file_path, width, height, format, size_bytes, aspect_ratio}.
    Supported formats: .png, .jpg, .jpeg, .gif, .webp, .bmp

    Args:
        file_path: Absolute path to the image file on disk.
    """
    try:
        with PILImage.open(file_path) as img:
            w, h = img.size
            fmt = img.format or os.path.splitext(file_path)[1].lstrip(".").upper()
        size_bytes = os.path.getsize(file_path)
        return {
            "file_path": file_path,
            "width": w,
            "height": h,
            "format": fmt.lower(),
            "size_bytes": size_bytes,
            "aspect_ratio": round(w / h, 4) if h else None,
        }
    except FileNotFoundError:
        return {"error": "NOT_FOUND", "message": f"File not found: {file_path}"}
    except Exception as e:
        return {"error": "READ_ERROR", "message": str(e)}


@mcp.tool()
async def batch_design(canvas_id: str, ops: list[dict]) -> list[dict]:
    """Execute multiple layer and shape operations in a single call.

    Operations run in order; results are returned in the same order.
    canvas_id is injected automatically — do not include it in individual ops.

    Each op must have an "action" key. Supported actions and their params:

      add_layer:       {name?}
      add_image:       {layer_id, file_path, x?, y?, width?, height?, opacity?}
      create_shape:    {layer_id, shape_type, x?, y?, width?, height?, radius?,
                        fill?, stroke?, stroke_width?, opacity?, rotation?,
                        text?, font_size?, font_family?, font_style?, align?,
                        points?, tension?, closed?, data?, num_points?,
                        inner_radius?, outer_radius?, sides?, angle?, clock_wise?}
      update_shape:    {shape_id, x?, y?, width?, height?, radius?,
                        fill?, stroke?, stroke_width?, opacity?, rotation?,
                        text?, font_size?, visible?}
      delete_shape:    {shape_id}
      transform_shape: {shape_id, operation, x?, y?, degrees?,
                        scale_x?, scale_y?, axis?}
                        operations: move | rotate | scale | flip
      clear_layer:     {layer_id}
      create_group:    {layer_id, shape_ids, x?, y?}

    shape_type values for create_shape:
      rect, circle, ellipse, line, arrow, text, path,
      star, regular_polygon, wedge, ring, arc
    """
    results = []
    for op in ops:
        op = {k: v for k, v in op.items() if v is not None}
        action = op.pop("action")
        op["canvas_id"] = canvas_id
        params = _camel_params(op)
        try:
            result = await _get_bridge().execute(action, params)
        except BridgeError as e:
            result = {"error": e.code, "message": str(e)}
        results.append({"action": action, **result})
    return results


def _get_bbox(attrs: dict) -> tuple[float, float, float, float] | None:
    """Return (x1, y1, x2, y2) axis-aligned bounding box from shape attrs, or None."""
    x, y = attrs.get("x", 0), attrs.get("y", 0)
    w, h = attrs.get("width"), attrs.get("height")
    r = attrs.get("radius")
    rx, ry = attrs.get("radiusX"), attrs.get("radiusY")
    outer_r = attrs.get("outerRadius")
    pts = attrs.get("points")

    if w is not None and h is not None:
        return (x, y, x + w, y + h)
    if r is not None:
        return (x - r, y - r, x + r, y + r)
    if rx is not None and ry is not None:
        return (x - rx, y - ry, x + rx, y + ry)
    if outer_r is not None:
        return (x - outer_r, y - outer_r, x + outer_r, y + outer_r)
    if pts and len(pts) >= 2:
        xs, ys = pts[0::2], pts[1::2]
        return (min(xs), min(ys), max(xs), max(ys))
    return None


def _boxes_overlap(a: tuple, b: tuple) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


@mcp.tool()
async def batch_get(canvas_id: str, queries: list[dict]) -> list[dict]:
    """Run multiple read queries against a canvas in a single call.

    Each query must have a "type" key. Supported types:

      canvas_state  — full canvas JSON hierarchy and shape index
      list_shapes   — all shapes with attrs; optional: {layer_id}
      find_shapes   — filtered shapes; optional: {layer_id, shape_type, text, fill}
                      text and fill are substring matches (case-insensitive)
    """
    results = []
    for query in queries:
        query = dict(query)
        qtype = query.pop("type")

        if qtype == "canvas_state":
            result = await _call("get_canvas_state", canvas_id=canvas_id)

        elif qtype == "list_shapes":
            result = await _call("list_shapes", canvas_id=canvas_id, layer_id=query.get("layer_id"))

        elif qtype == "find_shapes":
            base = await _call("list_shapes", canvas_id=canvas_id, layer_id=query.get("layer_id"))
            if "error" in base:
                result = base
            else:
                shapes = base.get("shapes", [])
                if st := query.get("shape_type"):
                    shapes = [s for s in shapes if s.get("type") == st]
                if txt := query.get("text"):
                    shapes = [s for s in shapes if txt.lower() in str(s.get("attrs", {}).get("text", "")).lower()]
                if fill := query.get("fill"):
                    shapes = [s for s in shapes if fill.lower() in str(s.get("attrs", {}).get("fill", "")).lower()]
                result = {"shapes": shapes, "count": len(shapes)}

        else:
            result = {"error": "UNKNOWN_QUERY", "message": f"Unknown query type: '{qtype}'"}

        results.append({"type": qtype, **result})
    return results


@mcp.tool()
async def snapshot_layout(canvas_id: str) -> dict:
    """Analyze the canvas layout structure and detect design issues.

    Returns:
      - canvas dimensions
      - per-layer shape counts
      - shapes with bounding boxes outside the canvas
      - pairs of overlapping shapes (by bounding box intersection)
    """
    shapes_res = await _call("list_shapes", canvas_id=canvas_id)
    state_res = await _call("get_canvas_state", canvas_id=canvas_id)

    if "error" in shapes_res:
        return shapes_res
    if "error" in state_res:
        return state_res

    shapes = shapes_res.get("shapes", [])
    stage_attrs = state_res.get("state", {}).get("attrs", {})
    canvas_w = stage_attrs.get("width", 0)
    canvas_h = stage_attrs.get("height", 0)

    # Layer summary
    layer_counts: dict[str, int] = {}
    for s in shapes:
        lid = s["layer_id"]
        layer_counts[lid] = layer_counts.get(lid, 0) + 1

    # Bounding boxes
    bboxes: dict[str, tuple] = {}
    for s in shapes:
        bb = _get_bbox(s.get("attrs", {}))
        if bb:
            bboxes[s["shape_id"]] = bb

    # Out-of-bounds detection
    out_of_bounds = []
    for s in shapes:
        bb = bboxes.get(s["shape_id"])
        if not bb:
            continue
        reasons = []
        if bb[0] < 0:          reasons.append("left edge out of bounds")
        if bb[1] < 0:          reasons.append("top edge out of bounds")
        if canvas_w and bb[2] > canvas_w: reasons.append("right edge out of bounds")
        if canvas_h and bb[3] > canvas_h: reasons.append("bottom edge out of bounds")
        if reasons:
            out_of_bounds.append({"shape_id": s["shape_id"], "type": s["type"], "issues": reasons})

    # Overlap detection (O(n²) on bboxed shapes)
    overlaps = []
    boxed = [s for s in shapes if s["shape_id"] in bboxes]
    for i in range(len(boxed)):
        for j in range(i + 1, len(boxed)):
            a, b = boxed[i], boxed[j]
            if _boxes_overlap(bboxes[a["shape_id"]], bboxes[b["shape_id"]]):
                overlaps.append({
                    "shape_a": a["shape_id"], "type_a": a["type"],
                    "shape_b": b["shape_id"], "type_b": b["type"],
                })

    return {
        "canvas": {"width": canvas_w, "height": canvas_h},
        "layers": [{"layer_id": lid, "shape_count": cnt} for lid, cnt in layer_counts.items()],
        "total_shapes": len(shapes),
        "out_of_bounds": out_of_bounds,
        "overlaps": overlaps,
    }


@mcp.tool()
async def preview_canvas(canvas_id: str, pixel_ratio: float = 1.0) -> Image:
    """Render the canvas and return it as an inline image for visual inspection.

    Call this after each major build phase to check layout, colours, and positioning.
    Use update_shape or delete_shape to fix anything that looks wrong, then continue.

    Args:
        canvas_id: ID returned by create_canvas.
        pixel_ratio: Rendering scale (1.0 = normal, 2.0 = retina).
    """
    bridge = _get_bridge()
    params = {"canvas_id": canvas_id, "pixelRatio": pixel_ratio}
    try:
        result = await bridge.execute("export_canvas", params)
    except BridgeError as e:
        return {"error": e.code, "message": str(e)}

    raw = base64.b64decode(result["data"])
    img = PILImage.open(BytesIO(raw))

    w, h = img.size
    if max(w, h) > _PREVIEW_MAX_DIM:
        scale = _PREVIEW_MAX_DIM / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), PILImage.LANCZOS)

    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=75, optimize=True)
    return Image(data=buf.getvalue(), format="jpeg")



@mcp.tool()
async def export_canvas(canvas_id: str, pixel_ratio: float = 1.0) -> dict:
    """Export the canvas as a PNG saved to a temp file.

    Returns {canvas_id, format, mime_type, file_path} pointing to the saved PNG.
    Use pixel_ratio=2.0 for high-DPI/retina output.
    """
    path = os.path.join(tempfile.gettempdir(), f"konva_{canvas_id}.png")
    return await _call("export_canvas", canvas_id=canvas_id, pixel_ratio=pixel_ratio, saveToFile=path)
