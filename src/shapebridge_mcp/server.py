"""ShapeBridge MCP Server implementation.

Provides stdio-based MCP server for Claude Code integration with
robust error handling and logging.
"""

from __future__ import annotations

import sys
from typing import Any, Dict

import structlog
from mcp.server.fastmcp import FastMCP

from .tools import (
    tool_export_view,
    tool_load_step,
    tool_session_info,
    tool_summarize_model,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(colors=False),  # No colors for stdio
    ],
    logger_factory=structlog.WriteLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Create FastMCP app
app = FastMCP("shapebridge")


@app.tool()
def load_step(path: str) -> Dict[str, Any]:
    """Load a STEP file from disk and register it in the session.

    Args:
        path: Absolute path to the STEP file

    Returns:
        Dictionary containing load results, model metadata, and session info

    Example:
        >>> load_step("/path/to/model.step")
        {
            "success": True,
            "model_id": "model",
            "file_path": "/path/to/model.step",
            "units": {"length": "mm", "angle": "deg"},
            "occt_binding": "pyOCCT",
            "file_size": 1024000
        }
    """
    try:
        logger.info("MCP tool: load_step", path=path)
        result = tool_load_step({"path": path})
        logger.info("MCP tool: load_step completed", success=result.get("success", False))
        return result
    except Exception as e:
        logger.error("MCP tool: load_step failed", path=path, error=str(e))
        return {
            "success": False,
            "error": f"Tool execution failed: {e}",
            "model_id": None,
            "file_path": path,
        }


@app.tool()
def summarize_model(model_id: str, out_dir: str | None = None) -> Dict[str, Any]:
    """Generate geometry summary and write STEPGraph-IR to disk.

    Analyzes the loaded model's topology, computes geometric properties,
    and generates a deterministic intermediate representation.

    Args:
        model_id: Identifier of the loaded model
        out_dir: Output directory for IR file (defaults to temp directory)

    Returns:
        Dictionary containing summary data and IR file path

    Example:
        >>> summarize_model("model", "/tmp")
        {
            "success": True,
            "model_id": "model",
            "summary": {
                "topology": {"faces": 100, "edges": 200, "vertices": 150},
                "units": {"length": "mm", "angle": "deg"}
            },
            "ir_path": "/tmp/model.jsonl"
        }
    """
    try:
        logger.info("MCP tool: summarize_model", model_id=model_id, out_dir=out_dir)
        params = {"model_id": model_id}
        if out_dir is not None:
            params["out_dir"] = out_dir

        result = tool_summarize_model(params)
        logger.info("MCP tool: summarize_model completed",
                   model_id=model_id, success=result.get("success", False))
        return result
    except Exception as e:
        logger.error("MCP tool: summarize_model failed", model_id=model_id, error=str(e))
        return {
            "success": False,
            "error": f"Tool execution failed: {e}",
            "model_id": model_id,
            "summary": None,
            "ir_path": None,
        }


@app.tool()
def export_view(model_id: str, format: str = "glb") -> Dict[str, Any]:
    """Export a 3D view of the loaded model.

    Generates a 3D representation suitable for visualization.
    Phase 0 returns placeholder data; Phase 1 will include real tessellation.

    Args:
        model_id: Identifier of the loaded model
        format: Export format ("glb" or "gltf")

    Returns:
        Dictionary containing export results with URI and data

    Example:
        >>> export_view("model", "glb")
        {
            "success": True,
            "model_id": "model",
            "format": "glb",
            "uri": "memory://model.glb",
            "data_base64": "Z2xURg..."
        }
    """
    try:
        logger.info("MCP tool: export_view", model_id=model_id, format=format)
        result = tool_export_view({"model_id": model_id, "format": format})
        logger.info("MCP tool: export_view completed",
                   model_id=model_id, format=format, success=result.get("success", False))
        return result
    except Exception as e:
        logger.error("MCP tool: export_view failed", model_id=model_id, format=format, error=str(e))
        return {
            "success": False,
            "error": f"Tool execution failed: {e}",
            "model_id": model_id,
            "format": format,
            "uri": None,
        }


@app.tool()
def session_info() -> Dict[str, Any]:
    """Get information about the current session and loaded models.

    Returns:
        Dictionary containing session statistics and model details

    Example:
        >>> session_info()
        {
            "success": True,
            "session_stats": {"loaded_models": 2, "max_models": 10},
            "models": [
                {"model_id": "part1", "file_path": "/path/to/part1.step"},
                {"model_id": "part2", "file_path": "/path/to/part2.step"}
            ]
        }
    """
    try:
        logger.info("MCP tool: session_info")
        result = tool_session_info()
        logger.info("MCP tool: session_info completed",
                   loaded_models=len(result.get("models", [])))
        return result
    except Exception as e:
        logger.error("MCP tool: session_info failed", error=str(e))
        return {
            "success": False,
            "error": f"Tool execution failed: {e}",
            "session_stats": {},
            "models": [],
        }


def main() -> None:
    """Main entry point for the MCP server.

    Runs the server in stdio mode for Claude Code integration.
    """
    try:
        logger.info("Starting ShapeBridge MCP server")

        # Log startup information
        from kernel.occt_io import get_occt_info
        occt_info = get_occt_info()
        logger.info("OCCT binding status", **occt_info)

        if not occt_info["pyOCCT_available"] and not occt_info["pythonOCC_available"]:
            logger.warning(
                "No OCCT binding available - STEP loading will fail. "
                "Install pyOCCT or pythonocc-core to enable geometry processing."
            )
        else:
            logger.info("OCCT binding available", recommended=occt_info["recommended_binding"])

        # Start the server
        logger.info("ShapeBridge MCP server ready")
        app.run()

    except KeyboardInterrupt:
        logger.info("MCP server shutting down (keyboard interrupt)")
        sys.exit(0)
    except Exception as e:
        logger.error("MCP server startup failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()