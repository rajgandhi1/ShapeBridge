"""Geometry analysis and summary generation.

This module provides functions to analyze CAD geometry and generate
summaries for the STEPGraph-IR representation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from .occt_io import LoadedModel

logger = structlog.get_logger(__name__)


@dataclass
class GeometrySummary:
    """Summary of geometric properties and topology."""

    model_id: str
    units: dict[str, str]

    # Topological counts
    solids: int = 0
    shells: int = 0
    faces: int = 0
    edges: int = 0
    vertices: int = 0

    # Geometric properties
    bounding_box: dict[str, float] | None = None
    surface_area: float | None = None
    volume: float | None = None

    # Analysis flags
    has_pmi: bool = False
    has_assemblies: bool = False
    has_curves: bool = False
    has_surfaces: bool = False

    # Metadata
    file_size: int = 0
    occt_binding: str = ""
    analysis_warnings: list[str] = None

    def __post_init__(self) -> None:
        """Initialize warnings list if None."""
        if self.analysis_warnings is None:
            self.analysis_warnings = []


def _count_topology_pyocct(shape: Any) -> dict[str, int]:
    """Count topological entities using pyOCCT.

    Args:
        shape: TopoDS_Shape from pyOCCT

    Returns:
        Dictionary with entity counts
    """
    try:
        from OCCT.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID, TopAbs_VERTEX
        from OCCT.TopExp import TopExp_Explorer

        counts = {
            "solids": 0,
            "shells": 0,
            "faces": 0,
            "edges": 0,
            "vertices": 0,
        }

        # Count each type of topological entity
        type_mappings = [
            (TopAbs_SOLID, "solids"),
            (TopAbs_SHELL, "shells"),
            (TopAbs_FACE, "faces"),
            (TopAbs_EDGE, "edges"),
            (TopAbs_VERTEX, "vertices"),
        ]

        for topo_type, count_key in type_mappings:
            explorer = TopExp_Explorer(shape, topo_type)
            count = 0
            while explorer.More():
                count += 1
                explorer.Next()
            counts[count_key] = count

        return counts

    except Exception as e:
        logger.warning("Failed to count topology with pyOCCT", error=str(e))
        return {"solids": 0, "shells": 0, "faces": 0, "edges": 0, "vertices": 0}


def _count_topology_pythonocc(shape: Any) -> dict[str, int]:
    """Count topological entities using pythonOCC.

    Args:
        shape: TopoDS_Shape from pythonOCC

    Returns:
        Dictionary with entity counts
    """
    try:
        from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID, TopAbs_VERTEX
        from OCP.TopExp import TopExp_Explorer

        counts = {
            "solids": 0,
            "shells": 0,
            "faces": 0,
            "edges": 0,
            "vertices": 0,
        }

        # Count each type of topological entity
        type_mappings = [
            (TopAbs_SOLID, "solids"),
            (TopAbs_SHELL, "shells"),
            (TopAbs_FACE, "faces"),
            (TopAbs_EDGE, "edges"),
            (TopAbs_VERTEX, "vertices"),
        ]

        for topo_type, count_key in type_mappings:
            explorer = TopExp_Explorer(shape, topo_type)
            count = 0
            while explorer.More():
                count += 1
                explorer.Next()
            counts[count_key] = count

        return counts

    except Exception as e:
        logger.warning("Failed to count topology with pythonOCC", error=str(e))
        return {"solids": 0, "shells": 0, "faces": 0, "edges": 0, "vertices": 0}


def _compute_bounding_box_pyocct(shape: Any) -> dict[str, float] | None:
    """Compute bounding box using pyOCCT.

    Args:
        shape: TopoDS_Shape from pyOCCT

    Returns:
        Bounding box dictionary or None if computation fails
    """
    try:
        from OCCT.Bnd import Bnd_Box
        from OCCT.BRepBndLib import BRepBndLib_Add

        bbox = Bnd_Box()
        BRepBndLib_Add(shape, bbox)

        if bbox.IsVoid():
            return None

        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

        return {
            "min_x": float(xmin),
            "min_y": float(ymin),
            "min_z": float(zmin),
            "max_x": float(xmax),
            "max_y": float(ymax),
            "max_z": float(zmax),
        }

    except Exception as e:
        logger.warning("Failed to compute bounding box with pyOCCT", error=str(e))
        return None


def _compute_bounding_box_pythonocc(shape: Any) -> dict[str, float] | None:
    """Compute bounding box using pythonOCC.

    Args:
        shape: TopoDS_Shape from pythonOCC

    Returns:
        Bounding box dictionary or None if computation fails
    """
    try:
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib_Add

        bbox = Bnd_Box()
        BRepBndLib_Add(shape, bbox)

        if bbox.IsVoid():
            return None

        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

        return {
            "min_x": float(xmin),
            "min_y": float(ymin),
            "min_z": float(zmin),
            "max_x": float(xmax),
            "max_y": float(ymax),
            "max_z": float(zmax),
        }

    except Exception as e:
        logger.warning("Failed to compute bounding box with pythonOCC", error=str(e))
        return None


def _compute_mass_properties_pyocct(shape: Any) -> tuple[float | None, float | None]:
    """Compute mass properties (surface area, volume) using pyOCCT.

    Args:
        shape: TopoDS_Shape from pyOCCT

    Returns:
        Tuple of (surface_area, volume) or (None, None) if computation fails
    """
    try:
        from OCCT.BRepGProp import BRepGProp_SurfaceProperties, BRepGProp_VolumeProperties
        from OCCT.GProp import GProp_GProps

        # Surface area
        surface_area = None
        try:
            surface_props = GProp_GProps()
            BRepGProp_SurfaceProperties(shape, surface_props)
            surface_area = float(surface_props.Mass())
        except Exception as e:
            logger.debug("Failed to compute surface area", error=str(e))

        # Volume
        volume = None
        try:
            volume_props = GProp_GProps()
            BRepGProp_VolumeProperties(shape, volume_props)
            volume = float(volume_props.Mass())
        except Exception as e:
            logger.debug("Failed to compute volume", error=str(e))

        return surface_area, volume

    except Exception as e:
        logger.warning("Failed to compute mass properties with pyOCCT", error=str(e))
        return None, None


def _compute_mass_properties_pythonocc(shape: Any) -> tuple[float | None, float | None]:
    """Compute mass properties (surface area, volume) using pythonOCC.

    Args:
        shape: TopoDS_Shape from pythonOCC

    Returns:
        Tuple of (surface_area, volume) or (None, None) if computation fails
    """
    try:
        from OCP.BRepGProp import BRepGProp_SurfaceProperties, BRepGProp_VolumeProperties
        from OCP.GProp import GProp_GProps

        # Surface area
        surface_area = None
        try:
            surface_props = GProp_GProps()
            BRepGProp_SurfaceProperties(shape, surface_props)
            surface_area = float(surface_props.Mass())
        except Exception as e:
            logger.debug("Failed to compute surface area", error=str(e))

        # Volume
        volume = None
        try:
            volume_props = GProp_GProps()
            BRepGProp_VolumeProperties(shape, volume_props)
            volume = float(volume_props.Mass())
        except Exception as e:
            logger.debug("Failed to compute volume", error=str(e))

        return surface_area, volume

    except Exception as e:
        logger.warning("Failed to compute mass properties with pythonOCC", error=str(e))
        return None, None


def _count_topology_freecad_occ(shape: Any) -> dict[str, int]:
    """Count topological entities using FreeCAD OCC.

    Args:
        shape: TopoDS_Shape from FreeCAD OCC

    Returns:
        Dictionary with entity counts
    """
    try:
        from OCC.Core.TopAbs import (
            TopAbs_EDGE,
            TopAbs_FACE,
            TopAbs_SHELL,
            TopAbs_SOLID,
            TopAbs_VERTEX,
        )
        from OCC.Core.TopExp import TopExp_Explorer

        counts = {
            "solids": 0,
            "shells": 0,
            "faces": 0,
            "edges": 0,
            "vertices": 0,
        }

        # Count each type of topological entity
        type_mappings = [
            (TopAbs_SOLID, "solids"),
            (TopAbs_SHELL, "shells"),
            (TopAbs_FACE, "faces"),
            (TopAbs_EDGE, "edges"),
            (TopAbs_VERTEX, "vertices"),
        ]

        for topo_type, count_key in type_mappings:
            explorer = TopExp_Explorer(shape, topo_type)
            count = 0
            while explorer.More():
                count += 1
                explorer.Next()
            counts[count_key] = count

        return counts

    except Exception as e:
        logger.warning("Failed to count topology with FreeCAD OCC", error=str(e))
        return {"solids": 0, "shells": 0, "faces": 0, "edges": 0, "vertices": 0}


def _compute_bounding_box_freecad_occ(shape: Any) -> dict[str, float] | None:
    """Compute bounding box using FreeCAD OCC.

    Args:
        shape: TopoDS_Shape from FreeCAD OCC

    Returns:
        Bounding box dictionary or None if computation fails
    """
    try:
        from OCC.Core.Bnd import Bnd_Box
        from OCC.Core.BRepBndLib import brepbndlib_Add

        bbox = Bnd_Box()
        brepbndlib_Add(shape, bbox)

        if bbox.IsVoid():
            return None

        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

        return {
            "min_x": float(xmin),
            "min_y": float(ymin),
            "min_z": float(zmin),
            "max_x": float(xmax),
            "max_y": float(ymax),
            "max_z": float(zmax),
        }

    except Exception as e:
        logger.warning("Failed to compute bounding box with FreeCAD OCC", error=str(e))
        return None


def _compute_mass_properties_freecad_occ(shape: Any) -> tuple[float | None, float | None]:
    """Compute mass properties (surface area, volume) using FreeCAD OCC.

    Args:
        shape: TopoDS_Shape from FreeCAD OCC

    Returns:
        Tuple of (surface_area, volume) or (None, None) if computation fails
    """
    try:
        from OCC.Core.BRepGProp import brepgprop_SurfaceProperties, brepgprop_VolumeProperties
        from OCC.Core.GProp import GProp_GProps

        # Surface area
        surface_area = None
        try:
            surface_props = GProp_GProps()
            brepgprop_SurfaceProperties(shape, surface_props)
            surface_area = float(surface_props.Mass())
        except Exception as e:
            logger.debug("Failed to compute surface area", error=str(e))

        # Volume
        volume = None
        try:
            volume_props = GProp_GProps()
            brepgprop_VolumeProperties(shape, volume_props)
            volume = float(volume_props.Mass())
        except Exception as e:
            logger.debug("Failed to compute volume", error=str(e))

        return surface_area, volume

    except Exception as e:
        logger.warning("Failed to compute mass properties with FreeCAD OCC", error=str(e))
        return None, None


def _analyze_geometry_content(shape: Any, binding: str) -> dict[str, bool]:
    """Analyze geometric content for presence of different entity types.

    Args:
        shape: TopoDS_Shape
        binding: OCCT binding name

    Returns:
        Dictionary with analysis flags
    """
    analysis = {
        "has_curves": False,
        "has_surfaces": False,
        "has_assemblies": False,
        "has_pmi": False,  # TODO: Implement PMI detection in Phase 1
    }

    try:
        if binding == "pyOCCT":
            from OCCT.TopAbs import TopAbs_EDGE, TopAbs_FACE
            from OCCT.TopExp import TopExp_Explorer

            # Check for edges (curves)
            edge_explorer = TopExp_Explorer(shape, TopAbs_EDGE)
            if edge_explorer.More():
                analysis["has_curves"] = True

            # Check for faces (surfaces)
            face_explorer = TopExp_Explorer(shape, TopAbs_FACE)
            if face_explorer.More():
                analysis["has_surfaces"] = True

        elif binding == "pythonOCC":
            from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
            from OCP.TopExp import TopExp_Explorer

            # Check for edges (curves)
            edge_explorer = TopExp_Explorer(shape, TopAbs_EDGE)
            if edge_explorer.More():
                analysis["has_curves"] = True

            # Check for faces (surfaces)
            face_explorer = TopExp_Explorer(shape, TopAbs_FACE)
            if face_explorer.More():
                analysis["has_surfaces"] = True

        elif binding == "freecad_occ":
            from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE
            from OCC.Core.TopExp import TopExp_Explorer

            # Check for edges (curves)
            edge_explorer = TopExp_Explorer(shape, TopAbs_EDGE)
            if edge_explorer.More():
                analysis["has_curves"] = True

            # Check for faces (surfaces)
            face_explorer = TopExp_Explorer(shape, TopAbs_FACE)
            if face_explorer.More():
                analysis["has_surfaces"] = True

    except Exception as e:
        logger.warning("Failed to analyze geometry content", binding=binding, error=str(e))

    return analysis


def summarize_shape(loaded_model: LoadedModel) -> GeometrySummary:
    """Generate a comprehensive summary of the loaded geometry.

    Args:
        loaded_model: LoadedModel containing the geometry

    Returns:
        GeometrySummary with topology counts and properties
    """
    logger.info("Generating geometry summary", model_id=loaded_model.model_id)

    warnings = []
    binding = loaded_model.occt_binding

    # Count topological entities
    if binding == "pyOCCT":
        topology_counts = _count_topology_pyocct(loaded_model.occt_shape)
        bounding_box = _compute_bounding_box_pyocct(loaded_model.occt_shape)
        surface_area, volume = _compute_mass_properties_pyocct(loaded_model.occt_shape)
    elif binding == "pythonOCC":
        topology_counts = _count_topology_pythonocc(loaded_model.occt_shape)
        bounding_box = _compute_bounding_box_pythonocc(loaded_model.occt_shape)
        surface_area, volume = _compute_mass_properties_pythonocc(loaded_model.occt_shape)
    elif binding == "freecad_occ":
        topology_counts = _count_topology_freecad_occ(loaded_model.occt_shape)
        bounding_box = _compute_bounding_box_freecad_occ(loaded_model.occt_shape)
        surface_area, volume = _compute_mass_properties_freecad_occ(loaded_model.occt_shape)
    else:
        logger.error("Unknown OCCT binding", binding=binding)
        topology_counts = {"solids": 0, "shells": 0, "faces": 0, "edges": 0, "vertices": 0}
        bounding_box = None
        surface_area, volume = None, None
        warnings.append(f"Unknown OCCT binding: {binding}")

    # Analyze geometric content
    content_analysis = _analyze_geometry_content(loaded_model.occt_shape, binding)

    # Check for potential issues
    if topology_counts["faces"] == 0 and topology_counts["edges"] > 0:
        warnings.append("Model contains only wireframe geometry (no surfaces)")

    if topology_counts["solids"] == 0 and topology_counts["faces"] > 0:
        warnings.append("Model contains surface geometry but no solids")

    if bounding_box is None:
        warnings.append("Could not compute bounding box")

    if surface_area is None:
        warnings.append("Could not compute surface area")

    if volume is None:
        warnings.append("Could not compute volume")

    # Create summary
    summary = GeometrySummary(
        model_id=loaded_model.model_id,
        units=loaded_model.units.copy(),
        solids=topology_counts["solids"],
        shells=topology_counts["shells"],
        faces=topology_counts["faces"],
        edges=topology_counts["edges"],
        vertices=topology_counts["vertices"],
        bounding_box=bounding_box,
        surface_area=surface_area,
        volume=volume,
        has_pmi=content_analysis["has_pmi"],
        has_assemblies=content_analysis["has_assemblies"],
        has_curves=content_analysis["has_curves"],
        has_surfaces=content_analysis["has_surfaces"],
        file_size=loaded_model.metadata.get("file_size", 0),
        occt_binding=binding,
        analysis_warnings=warnings,
    )

    logger.info(
        "Geometry summary completed",
        model_id=loaded_model.model_id,
        faces=summary.faces,
        edges=summary.edges,
        vertices=summary.vertices,
        warnings_count=len(warnings),
    )

    return summary


def create_placeholder_summary(model_id: str, error_message: str) -> GeometrySummary:
    """Create a placeholder summary when geometry analysis fails.

    Args:
        model_id: Model identifier
        error_message: Error description

    Returns:
        GeometrySummary with error information
    """
    return GeometrySummary(
        model_id=model_id,
        units={"length": "unknown", "angle": "unknown"},
        analysis_warnings=[f"Analysis failed: {error_message}"],
    )
