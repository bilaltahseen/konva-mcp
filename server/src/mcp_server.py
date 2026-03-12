from __future__ import annotations

import base64
import os
import tempfile
from typing import Optional, Literal

from fastmcp import FastMCP
from fastmcp.utilities.types import Image

from .bridge_client import BridgeClient, BridgeError

mcp = FastMCP(
    "konva-canvas",
    instructions=(
        "A 2D canvas tool powered by Konva.js. "
        "Build canvases in phases: create canvas and layers, then add shapes section by section. "
        "After each major section, call preview_canvas to visually inspect progress — "
        "use update_shape or delete_shape to correct anything that looks wrong before continuing. "
        "Call export_canvas only when the design is complete. "
        "All IDs returned by tools must be passed back to subsequent calls."
    ),
)

_bridge: BridgeClient | None = None


def _get_bridge() -> BridgeClient:
    if _bridge is None:
        raise RuntimeError("Bridge not initialized")
    return _bridge


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def _camel_params(d: dict) -> dict:
    skip = {"canvas_id", "layer_id", "shape_id", "group_id", "shape_type", "shape_ids",
            "operation", "axis", "format", "pixel_ratio", "name"}
    return {(_to_camel(k) if k not in skip else k): v for k, v in d.items()}


async def _call(action: str, **kwargs) -> dict:
    params = _camel_params(_clean(kwargs))
    try:
        return await _get_bridge().execute(action, params)
    except BridgeError as e:
        return {"error": e.code, "message": str(e)}


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
async def add_layer(canvas_id: str, name: Optional[str] = None) -> dict:
    """Add a new Layer to a canvas. Layers render bottom-to-top. Returns layer_id.

    Args:
        canvas_id: ID returned by create_canvas.
        name: Optional label for the layer.
    """
    return await _call("add_layer", canvas_id=canvas_id, name=name)


@mcp.tool()
async def create_shape(
    canvas_id: str,
    layer_id: str,
    shape_type: Literal["rect", "circle", "ellipse", "line", "arrow", "text",
                        "path", "star", "regular_polygon", "wedge", "ring", "arc"],
    x: float = 0,
    y: float = 0,
    width: Optional[float] = None,
    height: Optional[float] = None,
    radius: Optional[float] = None,
    fill: Optional[str] = None,
    stroke: Optional[str] = None,
    stroke_width: Optional[float] = None,
    opacity: Optional[float] = None,
    rotation: Optional[float] = None,
    text: Optional[str] = None,
    font_size: Optional[int] = None,
    font_family: Optional[str] = None,
    font_style: Optional[str] = None,
    align: Optional[str] = None,
    points: Optional[list[float]] = None,
    tension: Optional[float] = None,
    closed: Optional[bool] = None,
    data: Optional[str] = None,
    num_points: Optional[int] = None,
    inner_radius: Optional[float] = None,
    outer_radius: Optional[float] = None,
    sides: Optional[int] = None,
    angle: Optional[float] = None,
    clock_wise: Optional[bool] = None,
) -> dict:
    """Create a shape on the canvas. Returns shape_id and attrs.

    Required properties by shape_type:
    - rect: width, height
    - circle: radius
    - ellipse: width (radiusX), height (radiusY)
    - line/arrow: points=[x1,y1,x2,y2,...]
    - text: text, font_size
    - path: data (SVG path string d attribute)
    - star: num_points, inner_radius, outer_radius
    - regular_polygon: sides, radius
    - wedge: radius, angle
    - ring: inner_radius, outer_radius
    - arc: inner_radius, outer_radius, angle
    """
    params: dict = {
        "canvas_id": canvas_id, "layer_id": layer_id, "shape_type": shape_type,
        "x": x, "y": y,
    }
    optional_map = {
        "width": width, "height": height, "radius": radius,
        "fill": fill, "stroke": stroke, "strokeWidth": stroke_width,
        "opacity": opacity, "rotation": rotation,
        "text": text, "fontSize": font_size, "fontFamily": font_family,
        "fontStyle": font_style, "align": align,
        "points": points, "tension": tension, "closed": closed,
        "data": data,
        "numPoints": num_points, "innerRadius": inner_radius, "outerRadius": outer_radius,
        "sides": sides, "angle": angle, "clockwise": clock_wise,
    }
    params.update({k: v for k, v in optional_map.items() if v is not None})
    try:
        return await _get_bridge().execute("create_shape", params)
    except BridgeError as e:
        return {"error": e.code, "message": str(e)}


@mcp.tool()
async def update_shape(
    canvas_id: str,
    shape_id: str,
    x: Optional[float] = None,
    y: Optional[float] = None,
    width: Optional[float] = None,
    height: Optional[float] = None,
    radius: Optional[float] = None,
    fill: Optional[str] = None,
    stroke: Optional[str] = None,
    stroke_width: Optional[float] = None,
    opacity: Optional[float] = None,
    rotation: Optional[float] = None,
    text: Optional[str] = None,
    font_size: Optional[int] = None,
    visible: Optional[bool] = None,
) -> dict:
    """Update properties of an existing shape. Only provided (non-None) values are changed."""
    return await _call(
        "update_shape",
        canvas_id=canvas_id, shape_id=shape_id,
        x=x, y=y, width=width, height=height, radius=radius,
        fill=fill, stroke=stroke, stroke_width=stroke_width,
        opacity=opacity, rotation=rotation,
        text=text, font_size=font_size, visible=visible,
    )


@mcp.tool()
async def delete_shape(canvas_id: str, shape_id: str) -> dict:
    """Remove a shape from the canvas permanently."""
    return await _call("delete_shape", canvas_id=canvas_id, shape_id=shape_id)


@mcp.tool()
async def transform_shape(
    canvas_id: str,
    shape_id: str,
    operation: Literal["move", "rotate", "scale", "flip"],
    x: Optional[float] = None,
    y: Optional[float] = None,
    degrees: Optional[float] = None,
    scale_x: Optional[float] = None,
    scale_y: Optional[float] = None,
    axis: Optional[Literal["horizontal", "vertical"]] = None,
) -> dict:
    """Apply a 2D transformation to a shape.

    Operations:
    - move: set absolute position (x, y)
    - rotate: set absolute rotation in degrees
    - scale: set scale factors (scale_x, scale_y; 1.0 = original size)
    - flip: mirror along axis ("horizontal" or "vertical")
    """
    params: dict = {"canvas_id": canvas_id, "shape_id": shape_id, "operation": operation}
    if x is not None:       params["x"] = x
    if y is not None:       params["y"] = y
    if degrees is not None: params["degrees"] = degrees
    if scale_x is not None: params["scaleX"] = scale_x
    if scale_y is not None: params["scaleY"] = scale_y
    if axis is not None:    params["axis"] = axis
    try:
        return await _get_bridge().execute("transform_shape", params)
    except BridgeError as e:
        return {"error": e.code, "message": str(e)}


@mcp.tool()
async def list_shapes(canvas_id: str, layer_id: Optional[str] = None) -> dict:
    """List all shapes on the canvas with IDs, types, and attributes. Filter by layer_id."""
    return await _call("list_shapes", canvas_id=canvas_id, layer_id=layer_id)


@mcp.tool()
async def clear_layer(canvas_id: str, layer_id: str) -> dict:
    """Remove all shapes from a layer. The layer itself remains."""
    return await _call("clear_layer", canvas_id=canvas_id, layer_id=layer_id)


@mcp.tool()
async def create_group(
    canvas_id: str,
    layer_id: str,
    shape_ids: list[str],
    x: float = 0,
    y: float = 0,
) -> dict:
    """Group multiple shapes into a single addressable unit.

    Transformations on the group affect all children. Returns group_id.
    """
    params = {"canvas_id": canvas_id, "layer_id": layer_id,
              "shape_ids": shape_ids, "x": x, "y": y}
    try:
        return await _get_bridge().execute("create_group", params)
    except BridgeError as e:
        return {"error": e.code, "message": str(e)}


@mcp.tool()
async def get_canvas_state(canvas_id: str) -> dict:
    """Return the full JSON state of the canvas including all layers and shapes."""
    return await _call("get_canvas_state", canvas_id=canvas_id)


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
    return Image(data=raw, format="png")


@mcp.tool()
async def export_canvas(canvas_id: str, pixel_ratio: float = 1.0) -> dict:
    """Export the canvas as a PNG saved to a temp file.

    Returns {canvas_id, format, mime_type, file_path} pointing to the saved PNG.
    Use pixel_ratio=2.0 for high-DPI/retina output.
    """
    path = os.path.join(tempfile.gettempdir(), f"konva_{canvas_id}.png")
    return await _call("export_canvas", canvas_id=canvas_id, pixel_ratio=pixel_ratio, saveToFile=path)
