# konva-mcp

An MCP (Model Context Protocol) server that gives AI assistants the ability to draw on a 2D canvas using [Konva.js](https://konvajs.org/), running headlessly on Node.js.

## Architecture

```
Claude ←stdio→ Python MCP (FastMCP) ←HTTP→ Node.js bridge (Express + Konva)
```

- **Python MCP server** (`server/`) — exposes 9 tools over stdio using FastMCP, proxies calls to the bridge.
- **Node.js bridge** (`bridge/`) — runs Konva.js headlessly via the `canvas` package, manages canvas state, renders PNGs.

## Prerequisites

- [Node.js](https://nodejs.org/) (v18+)
- [Python](https://www.python.org/) 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Installation

```bash
# Install Node.js bridge dependencies
cd bridge
npm install

# Python dependencies are managed automatically by uv — no manual step needed
```

## Usage

### Run as MCP server (for Claude Desktop or Claude Code)

```bash
cd server
uv run python main.py                                      # stdio (default)
uv run python main.py --transport sse                      # SSE on 127.0.0.1:8000
uv run python main.py --transport http --host 0.0.0.0 --port 9000  # streamable HTTP
```

The server starts the Node.js bridge as a subprocess, waits for it to be ready, then begins accepting MCP requests on the chosen transport.

| Flag | Default | Description |
|---|---|---|
| `--transport` | `stdio` | Transport: `stdio`, `sse`, or `http` |
| `--host` | `127.0.0.1` | Bind host (sse/http only) |
| `--port` | `8000` | Bind port (sse/http only) |

### Claude Desktop config

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "konva-canvas": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/konva-mcp/server", "python", "main.py", "--transport", "stdio"]
    }
  }
}
```

### Claude Code config (`.mcp.json`)

```json
{
  "mcpServers": {
    "konva-canvas": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/konva-mcp/server", "python", "main.py", "--transport", "stdio"]
    }
  }
}
```

### Run the bridge standalone (for testing)

```bash
cd bridge
node server.js
```

The bridge listens on a random free port by default (overridable via `BRIDGE_PORT` env var) and prints `BRIDGE_READY` when ready.

## Tools

| Tool | Description |
|---|---|
| `create_canvas` | Create a new canvas (Stage + default layer). Returns `canvas_id` and `layer_id`. |
| `batch_design` | Execute multiple layer/shape operations in one call (see actions below). |
| `image_info` | Return metadata (dimensions, format) for an image file without placing it. |
| `load_font` | Register a custom font file for use in text shapes. |
| `batch_get` | Run multiple read queries in one call (see query types below). |
| `snapshot_layout` | Analyze layout structure, detect out-of-bounds and overlapping elements. |
| `preview_canvas` | Render the canvas and return it as an inline image for visual inspection. |
| `export_canvas` | Export the finished canvas as a PNG file. |
### `batch_get` query types

Pass `queries` as a list of objects, each with a `"type"` key. `canvas_id` is injected automatically.

| Type | Description | Optional params |
|---|---|---|
| `canvas_state` | Full Konva JSON hierarchy and shape index | — |
| `list_shapes` | All shapes with attrs | `layer_id` |
| `find_shapes` | Filtered shapes (substring match) | `layer_id`, `shape_type`, `text`, `fill` |

### `batch_design` actions

Pass `ops` as a list of objects, each with an `"action"` key. `canvas_id` is injected automatically.

| Action | Required params | Optional params |
|---|---|---|
| `add_layer` | — | `name` |
| `add_image` | `layer_id`, `file_path` | `x`, `y`, `width`, `height`, `opacity` |
| `create_shape` | `layer_id`, `shape_type` | `x`, `y`, `width`, `height`, `radius`, `fill`, `stroke`, `stroke_width`, `opacity`, `rotation`, `text`, `font_size`, `font_family`, `font_style`, `align`, `points`, `tension`, `closed`, `data`, `num_points`, `inner_radius`, `outer_radius`, `sides`, `angle`, `clock_wise` |
| `update_shape` | `shape_id` | `x`, `y`, `width`, `height`, `radius`, `fill`, `stroke`, `stroke_width`, `opacity`, `rotation`, `text`, `font_size`, `visible` |
| `delete_shape` | `shape_id` | — |
| `transform_shape` | `shape_id`, `operation` | `x`, `y`, `degrees`, `scale_x`, `scale_y`, `axis` |
| `clear_layer` | `layer_id` | — |
| `create_group` | `layer_id`, `shape_ids` | `x`, `y` |

`shape_type` values: `rect`, `circle`, `ellipse`, `line`, `arrow`, `text`, `path`, `star`, `regular_polygon`, `wedge`, `ring`, `arc`

`transform_shape` operations: `move`, `rotate`, `scale`, `flip`

### Recommended workflow

1. `create_canvas` → get `canvas_id` and `layer_id`
2. `batch_design` to add layers and shapes in bulk
3. `preview_canvas` after each major section to visually inspect progress
4. Fix issues with another `batch_design` call (`update_shape` / `delete_shape` actions)
5. `export_canvas` when the design is complete

## Project structure

```
konva-mcp/
├── bridge/
│   ├── server.js              # Express entry point
│   └── src/
│       ├── canvasManager.js   # Canvas state (Map of canvas_id → Stage)
│       └── handlers/          # Action dispatcher and per-action handlers
└── server/
    ├── main.py                # Entry point: finds free port, starts bridge, runs MCP
    ├── pyproject.toml
        └── src/
        ├── mcp_server.py      # FastMCP tool definitions (9 tools)
        ├── bridge_client.py   # httpx async HTTP client
        └── bridge_process.py  # asyncio subprocess manager
```

## Dependencies

**Node.js bridge**
- `konva` ^10.2.0 — 2D canvas library
- `canvas` ^3.2.1 — headless Canvas API for Node.js
- `express` ^5.2.1 — HTTP server
- `nanoid` ^5 — unique ID generation

**Python MCP server**
- `fastmcp` >=3.1.0 — MCP server framework
- `httpx` >=0.28.1 — async HTTP client
