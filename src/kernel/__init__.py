"""Kernel package for CAD geometry processing.

This package provides the core functionality for STEP file ingestion,
geometry analysis, and export operations using Open CASCADE Technology.
"""

from .occt_io import LoadedModel, StepImportError, load_step, get_occt_info
from .summary import summarize_shape, GeometrySummary
from .export import export_glb_placeholder, ExportError

__version__ = "0.1.0"
__all__ = [
    "LoadedModel", "StepImportError", "load_step", "get_occt_info",
    "summarize_shape", "GeometrySummary",
    "export_glb_placeholder", "ExportError"
]