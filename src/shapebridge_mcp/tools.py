"""MCP tools implementation with session management.

This module provides the core tools for the ShapeBridge MCP server
with proper error handling and session management.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from kernel.export import export_model_view, ExportError
from kernel.occt_io import LoadedModel, load_step, OCCTNotAvailableError, StepImportError
from kernel.summary import GeometrySummary, summarize_shape, create_placeholder_summary
from stepgraph_ir.schema import IR, Node, Edge, ValidationInfo, create_part_node
from stepgraph_ir.serialize import dump_jsonl

logger = structlog.get_logger(__name__)


class SessionError(Exception):
    """Raised when session operations fail."""
    pass


class ShapeBridgeSession:
    """Session manager for loaded models and operations."""

    def __init__(self, max_models: int = 10):
        """Initialize session.

        Args:
            max_models: Maximum number of models to keep in memory
        """
        self._models: Dict[str, LoadedModel] = {}
        self._summaries: Dict[str, GeometrySummary] = {}
        self._max_models = max_models
        self._load_times: Dict[str, float] = {}

        logger.info("ShapeBridge session initialized", max_models=max_models)

    def cleanup_old_models(self) -> None:
        """Remove oldest models if we exceed the limit."""
        if len(self._models) <= self._max_models:
            return

        # Sort by load time and remove oldest
        sorted_models = sorted(self._load_times.items(), key=lambda x: x[1])
        models_to_remove = sorted_models[:-self._max_models]

        for model_id, _ in models_to_remove:
            self.remove_model(model_id)

    def remove_model(self, model_id: str) -> None:
        """Remove a model from the session."""
        if model_id in self._models:
            del self._models[model_id]
            logger.debug("Removed model from session", model_id=model_id)

        if model_id in self._summaries:
            del self._summaries[model_id]

        if model_id in self._load_times:
            del self._load_times[model_id]

    def has_model(self, model_id: str) -> bool:
        """Check if a model is loaded in the session."""
        return model_id in self._models

    def get_model(self, model_id: str) -> Optional[LoadedModel]:
        """Get a loaded model by ID."""
        return self._models.get(model_id)

    def get_summary(self, model_id: str) -> Optional[GeometrySummary]:
        """Get a model summary by ID."""
        return self._summaries.get(model_id)

    def list_models(self) -> List[str]:
        """Get list of loaded model IDs."""
        return list(self._models.keys())

    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        return {
            "loaded_models": len(self._models),
            "max_models": self._max_models,
            "model_ids": list(self._models.keys()),
        }

    def load_model(self, file_path: str) -> LoadedModel:
        """Load a STEP file and add to session.

        Args:
            file_path: Path to STEP file

        Returns:
            LoadedModel instance

        Raises:
            SessionError: If loading fails
        """
        try:
            logger.info("Loading STEP model", file_path=file_path)

            # Load the model
            loaded_model = load_step(file_path)

            # Store in session
            self._models[loaded_model.model_id] = loaded_model
            self._load_times[loaded_model.model_id] = time.time()

            # Cleanup old models if needed
            self.cleanup_old_models()

            logger.info(
                "Model loaded successfully",
                model_id=loaded_model.model_id,
                file_path=file_path,
                units=loaded_model.units,
                binding=loaded_model.occt_binding
            )

            return loaded_model

        except (StepImportError, OCCTNotAvailableError) as e:
            logger.error("Failed to load STEP model", file_path=file_path, error=str(e))
            raise SessionError(f"Failed to load STEP file: {e}") from e

    def generate_summary(self, model_id: str) -> GeometrySummary:
        """Generate geometry summary for a loaded model.

        Args:
            model_id: Model identifier

        Returns:
            GeometrySummary instance

        Raises:
            SessionError: If model not found or analysis fails
        """
        if model_id not in self._models:
            raise SessionError(f"Model not found in session: {model_id}")

        try:
            logger.info("Generating geometry summary", model_id=model_id)

            loaded_model = self._models[model_id]
            summary = summarize_shape(loaded_model)

            # Cache the summary
            self._summaries[model_id] = summary

            logger.info(
                "Summary generated successfully",
                model_id=model_id,
                faces=summary.faces,
                edges=summary.edges,
                vertices=summary.vertices
            )

            return summary

        except Exception as e:
            logger.error("Failed to generate summary", model_id=model_id, error=str(e))
            # Create placeholder summary for failed analysis
            summary = create_placeholder_summary(model_id, str(e))
            self._summaries[model_id] = summary
            return summary

    def export_view(self, model_id: str, format: str = "glb") -> Dict[str, Any]:
        """Export 3D view of a loaded model.

        Args:
            model_id: Model identifier
            format: Export format ("glb" or "gltf")

        Returns:
            Export result dictionary

        Raises:
            SessionError: If model not found or export fails
        """
        if model_id not in self._models:
            raise SessionError(f"Model not found in session: {model_id}")

        try:
            logger.info("Exporting model view", model_id=model_id, format=format)

            loaded_model = self._models[model_id]
            result = export_model_view(loaded_model, format=format)

            logger.info(
                "Export completed successfully",
                model_id=model_id,
                format=format,
                uri=result.get("uri", "unknown")
            )

            return result

        except ExportError as e:
            logger.error("Failed to export model view", model_id=model_id, format=format, error=str(e))
            raise SessionError(f"Failed to export model view: {e}") from e


# Global session instance for MCP tools
_session = ShapeBridgeSession()


def tool_load_step(params: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool: Load a STEP file from disk.

    Args:
        params: Tool parameters containing 'path'

    Returns:
        Dictionary with load results

    Raises:
        ValueError: If parameters are invalid
        SessionError: If loading fails
    """
    if "path" not in params:
        raise ValueError("Missing required parameter: path")

    file_path = params["path"]
    if not file_path:
        raise ValueError("Parameter 'path' cannot be empty")

    # Validate file path
    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"File not found: {file_path}")

    try:
        loaded_model = _session.load_model(file_path)

        return {
            "success": True,
            "model_id": loaded_model.model_id,
            "file_path": loaded_model.file_path,
            "units": loaded_model.units,
            "occt_binding": loaded_model.occt_binding,
            "occt_version": loaded_model.occt_version,
            "file_size": loaded_model.metadata.get("file_size", 0),
            "session_stats": _session.get_session_stats(),
        }

    except SessionError as e:
        logger.error("load_step tool failed", file_path=file_path, error=str(e))
        return {
            "success": False,
            "error": str(e),
            "model_id": None,
            "file_path": file_path,
        }


def tool_summarize_model(params: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool: Generate geometry summary and IR for a loaded model.

    Args:
        params: Tool parameters containing 'model_id' and optional 'out_dir'

    Returns:
        Dictionary with summary and IR path

    Raises:
        ValueError: If parameters are invalid
        SessionError: If model not found or analysis fails
    """
    if "model_id" not in params:
        raise ValueError("Missing required parameter: model_id")

    model_id = params["model_id"]
    if not model_id:
        raise ValueError("Parameter 'model_id' cannot be empty")

    out_dir = params.get("out_dir", tempfile.gettempdir())

    try:
        # Generate summary
        summary = _session.generate_summary(model_id)

        # Create minimal IR for Phase 0
        ir = _create_minimal_ir(model_id, summary)

        # Write IR to file
        out_path = Path(out_dir) / f"{model_id}.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        dump_jsonl(ir, out_path)

        logger.info("IR written successfully", model_id=model_id, path=str(out_path))

        return {
            "success": True,
            "model_id": model_id,
            "summary": {
                "units": summary.units,
                "topology": {
                    "solids": summary.solids,
                    "shells": summary.shells,
                    "faces": summary.faces,
                    "edges": summary.edges,
                    "vertices": summary.vertices,
                },
                "properties": {
                    "bounding_box": summary.bounding_box,
                    "surface_area": summary.surface_area,
                    "volume": summary.volume,
                },
                "analysis": {
                    "has_pmi": summary.has_pmi,
                    "has_assemblies": summary.has_assemblies,
                    "has_curves": summary.has_curves,
                    "has_surfaces": summary.has_surfaces,
                },
                "metadata": {
                    "file_size": summary.file_size,
                    "occt_binding": summary.occt_binding,
                    "warnings": summary.analysis_warnings,
                }
            },
            "ir_path": str(out_path),
            "ir_valid": ir.validation.is_valid,
        }

    except SessionError as e:
        logger.error("summarize_model tool failed", model_id=model_id, error=str(e))
        return {
            "success": False,
            "error": str(e),
            "model_id": model_id,
            "summary": None,
            "ir_path": None,
        }


def tool_export_view(params: Dict[str, Any]) -> Dict[str, Any]:
    """MCP tool: Export 3D view of a loaded model.

    Args:
        params: Tool parameters containing 'model_id' and optional 'format'

    Returns:
        Dictionary with export results

    Raises:
        ValueError: If parameters are invalid
        SessionError: If model not found or export fails
    """
    if "model_id" not in params:
        raise ValueError("Missing required parameter: model_id")

    model_id = params["model_id"]
    if not model_id:
        raise ValueError("Parameter 'model_id' cannot be empty")

    format = params.get("format", "glb").lower()
    if format not in ("glb", "gltf"):
        raise ValueError(f"Unsupported format: {format}. Use 'glb' or 'gltf'")

    try:
        result = _session.export_view(model_id, format=format)

        return {
            "success": True,
            "model_id": model_id,
            "format": result["format"],
            "uri": result["uri"],
            "mime_type": result["mime_type"],
            "size_bytes": result.get("size_bytes"),
            "data_base64": result.get("data_base64"),  # For GLB
            "data": result.get("data"),  # For GLTF JSON
        }

    except SessionError as e:
        logger.error("export_view tool failed", model_id=model_id, format=format, error=str(e))
        return {
            "success": False,
            "error": str(e),
            "model_id": model_id,
            "format": format,
            "uri": None,
        }


def tool_session_info(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """MCP tool: Get session information and loaded models.

    Args:
        params: Optional parameters (unused)

    Returns:
        Dictionary with session information
    """
    stats = _session.get_session_stats()

    # Add detailed model info
    model_details = []
    for model_id in stats["model_ids"]:
        model = _session.get_model(model_id)
        summary = _session.get_summary(model_id)

        detail = {
            "model_id": model_id,
            "file_path": model.file_path if model else "unknown",
            "units": model.units if model else {},
            "occt_binding": model.occt_binding if model else "unknown",
            "has_summary": summary is not None,
        }

        if summary:
            detail["topology"] = {
                "faces": summary.faces,
                "edges": summary.edges,
                "vertices": summary.vertices,
            }

        model_details.append(detail)

    return {
        "success": True,
        "session_stats": stats,
        "models": model_details,
        "available_tools": [
            "load_step",
            "summarize_model",
            "export_view",
            "session_info"
        ]
    }


def _create_minimal_ir(model_id: str, summary: GeometrySummary) -> IR:
    """Create minimal IR representation for Phase 0.

    Args:
        model_id: Model identifier
        summary: Geometry summary

    Returns:
        IR instance with minimal node/edge structure
    """
    # Create root part node
    part_node = create_part_node(model_id, node_id=f"{model_id}_root")
    part_node.attrs.update({
        "topology": {
            "solids": summary.solids,
            "faces": summary.faces,
            "edges": summary.edges,
            "vertices": summary.vertices,
        },
        "analysis": {
            "has_surfaces": summary.has_surfaces,
            "has_curves": summary.has_curves,
        },
        "occt_binding": summary.occt_binding,
    })

    if summary.bounding_box:
        part_node.attrs["bounding_box"] = summary.bounding_box

    if summary.surface_area is not None:
        part_node.attrs["surface_area"] = summary.surface_area

    if summary.volume is not None:
        part_node.attrs["volume"] = summary.volume

    # Create IR with validation info
    validation = ValidationInfo()
    if summary.analysis_warnings:
        validation.warnings.extend(summary.analysis_warnings)

    ir = IR(
        model_id=model_id,
        nodes=[part_node],
        edges=[],
        units=summary.units,
        provenance={
            "phase": "0",
            "generator": "ShapeBridge Phase 0",
            "occt_binding": summary.occt_binding,
            "file_size": summary.file_size,
        },
        validation=validation,
    )

    return ir