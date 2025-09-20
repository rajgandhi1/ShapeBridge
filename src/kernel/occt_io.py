"""STEP file import and Open CASCADE integration.

This module provides robust STEP file loading with fallback between
different OCCT Python bindings (pyOCCT and pythonOCC-core).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class StepImportError(Exception):
    """Raised when STEP file import fails."""

    pass


class OCCTNotAvailableError(Exception):
    """Raised when no OCCT binding is available."""

    pass


@dataclass
class LoadedModel:
    """Container for a successfully loaded STEP model."""

    model_id: str
    file_path: str
    occt_shape: Any  # TopoDS_Shape (kept opaque for type safety)
    units: dict[str, str]
    metadata: dict[str, Any]

    # Binding information
    occt_binding: str  # "pyOCCT", "pythonOCC", or "freecad_occ"
    occt_version: str

    def __post_init__(self) -> None:
        """Validate loaded model."""
        if not self.model_id:
            self.model_id = Path(self.file_path).stem

        # Ensure required metadata
        if "file_size" not in self.metadata:
            try:
                self.metadata["file_size"] = os.path.getsize(self.file_path)
            except OSError:
                self.metadata["file_size"] = -1


def get_occt_info() -> dict[str, Any]:
    """Get information about available OCCT bindings.

    Returns:
        Dictionary with binding availability and version info
    """
    info = {
        "pyOCCT_available": False,
        "pythonOCC_available": False,
        "freecad_occ_available": False,
        "recommended_binding": None,
        "occt_version": None,
    }

    # Check pyOCCT availability
    try:
        import OCCT

        info["pyOCCT_available"] = True
        info["recommended_binding"] = "pyOCCT"
        try:
            # Try to get version info
            if hasattr(OCCT, "__version__"):
                info["occt_version"] = OCCT.__version__
        except Exception:
            pass
        logger.info("pyOCCT binding detected")
    except ImportError:
        logger.debug("pyOCCT not available")

    # Check pythonOCC availability
    try:
        import OCP

        info["pythonOCC_available"] = True
        if not info["recommended_binding"]:
            info["recommended_binding"] = "pythonOCC"
        try:
            # Try to get version info
            if hasattr(OCP, "__version__"):
                info["occt_version"] = OCP.__version__
        except Exception:
            pass
        logger.info("pythonOCC binding detected")
    except ImportError:
        logger.debug("pythonOCC not available")

    # Check conda pythonocc-core availability (uses OCC.Core like FreeCAD)
    try:
        import OCC

        # Check if this is conda pythonocc-core vs FreeCAD by checking module path
        occ_path = OCC.__file__
        if "conda" in occ_path or "anaconda" in occ_path:
            info["pythonOCC_available"] = True
            info["freecad_occ_available"] = False
            if not info["recommended_binding"]:
                info["recommended_binding"] = "pythonOCC"
            logger.info("conda pythonocc-core binding detected")
        else:
            info["freecad_occ_available"] = True
            if not info["recommended_binding"]:
                info["recommended_binding"] = "freecad_occ"
            logger.info("FreeCAD OCC binding detected")
    except ImportError:
        logger.debug("OCC.Core not available")

    return info


def _validate_step_file(file_path: str | Path) -> Path:
    """Validate STEP file exists and is readable.

    Args:
        file_path: Path to STEP file

    Returns:
        Validated Path object

    Raises:
        StepImportError: If file validation fails
    """
    path = Path(file_path).resolve()

    if not path.exists():
        raise StepImportError(f"STEP file not found: {path}")

    if not path.is_file():
        raise StepImportError(f"Path is not a file: {path}")

    if path.stat().st_size == 0:
        raise StepImportError(f"STEP file is empty: {path}")

    # Basic STEP file validation
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            header = f.read(1024)
            if not header.startswith("ISO-10303-"):
                logger.warning("File does not start with ISO-10303 header", file=str(path))
    except Exception as e:
        logger.warning("Could not validate STEP header", file=str(path), error=str(e))

    return path


def _extract_step_units(file_path: Path) -> dict[str, str]:
    """Extract unit information from STEP file header.

    Args:
        file_path: Path to STEP file

    Returns:
        Dictionary mapping unit types to unit names
    """
    default_units = {"length": "mm", "angle": "deg"}

    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            # Read header section (usually first ~50 lines)
            header_lines = []
            for i, line in enumerate(f):
                header_lines.append(line.strip())
                if i > 50 or line.strip() == "ENDSEC;":
                    break

        header_text = " ".join(header_lines).upper()

        # Simple unit detection
        units = default_units.copy()

        if "MILLIMETRE" in header_text or "MM" in header_text:
            units["length"] = "mm"
        elif "METRE" in header_text and "MILLIMETRE" not in header_text:
            units["length"] = "m"
        elif "INCH" in header_text:
            units["length"] = "in"

        if "DEGREE" in header_text:
            units["angle"] = "deg"
        elif "RADIAN" in header_text:
            units["angle"] = "rad"

        return units

    except Exception as e:
        logger.warning("Could not extract units from STEP file", file=str(file_path), error=str(e))
        return default_units


def _try_pyocct_import(file_path: Path) -> LoadedModel | None:
    """Attempt to load STEP file using pyOCCT binding.

    Args:
        file_path: Path to STEP file

    Returns:
        LoadedModel if successful, None if failed
    """
    try:
        import OCCT
        from OCCT.IFSelect import IFSelect_RetDone
        from OCCT.Interface import Interface_Static
        from OCCT.STEPControl import STEPControl_Reader

        logger.debug("Attempting STEP import with pyOCCT", file=str(file_path))

        # Create reader and configure
        reader = STEPControl_Reader()

        # Set some common options for better compatibility
        Interface_Static.SetCVal("xstep.cascade.unit", "mm")
        Interface_Static.SetRVal("read.precision.mode", 1)
        Interface_Static.SetRVal("read.precision.val", 0.01)

        # Read file
        status = reader.ReadFile(str(file_path))
        if status != IFSelect_RetDone:
            raise StepImportError(f"pyOCCT read failed with status: {status}")

        # Transfer geometry
        nb_roots = reader.NbRootsForTransfer()
        if nb_roots == 0:
            raise StepImportError("No geometry roots found in STEP file")

        logger.debug("Found geometry roots", count=nb_roots)
        reader.TransferRoots()

        # Get the unified shape
        shape = reader.OneShape()
        if shape.IsNull():
            raise StepImportError("Failed to create unified shape from STEP file")

        # Extract units and metadata
        units = _extract_step_units(file_path)

        # Try to get more detailed unit info from OCCT
        try:
            length_unit = Interface_Static.CVal("xstep.cascade.unit")
            if length_unit:
                units["length"] = (
                    length_unit.decode() if isinstance(length_unit, bytes) else str(length_unit)
                )
        except Exception:
            pass

        metadata = {
            "nb_roots": nb_roots,
            "reader_type": "STEPControl_Reader",
            "file_size": file_path.stat().st_size,
        }

        # Get version info
        occt_version = getattr(OCCT, "__version__", "unknown")

        return LoadedModel(
            model_id=file_path.stem,
            file_path=str(file_path),
            occt_shape=shape,
            units=units,
            metadata=metadata,
            occt_binding="pyOCCT",
            occt_version=occt_version,
        )

    except ImportError:
        logger.debug("pyOCCT not available")
        return None
    except Exception as e:
        logger.warning("pyOCCT import failed", file=str(file_path), error=str(e))
        return None


def _try_pythonocc_import(file_path: Path) -> LoadedModel | None:
    """Attempt to load STEP file using pythonOCC binding.

    Args:
        file_path: Path to STEP file

    Returns:
        LoadedModel if successful, None if failed
    """
    try:
        # Try OCP import first (classic pythonOCC)
        try:
            import OCP
            from OCP.IFSelect import IFSelect_RetDone
            from OCP.Interface import Interface_Static
            from OCP.STEPControl import STEPControl_Reader

            logger.debug("Attempting STEP import with pythonOCC (OCP)", file=str(file_path))
            version_module = OCP
        except ImportError:
            # Try OCC.Core import (conda pythonocc-core)
            import OCC
            from OCC.Core.IFSelect import IFSelect_RetDone
            from OCC.Core.Interface import Interface_Static
            from OCC.Core.STEPControl import STEPControl_Reader

            # Verify this is conda pythonocc-core and not FreeCAD
            if "conda" not in OCC.__file__ and "anaconda" not in OCC.__file__:
                raise ImportError("FreeCAD OCC detected, not conda pythonocc-core") from None
            logger.debug(
                "Attempting STEP import with conda pythonocc-core (OCC.Core)", file=str(file_path)
            )
            version_module = OCC

        # Create reader and configure
        reader = STEPControl_Reader()

        # Set some common options for better compatibility
        Interface_Static.SetCVal("xstep.cascade.unit", "mm")
        Interface_Static.SetRVal("read.precision.mode", 1)
        Interface_Static.SetRVal("read.precision.val", 0.01)

        # Read file
        status = reader.ReadFile(str(file_path))
        if status != IFSelect_RetDone:
            raise StepImportError(f"pythonOCC read failed with status: {status}")

        # Transfer geometry
        nb_roots = reader.NbRootsForTransfer()
        if nb_roots == 0:
            raise StepImportError("No geometry roots found in STEP file")

        logger.debug("Found geometry roots", count=nb_roots)
        reader.TransferRoots()

        # Get the unified shape
        shape = reader.OneShape()
        if shape.IsNull():
            raise StepImportError("Failed to create unified shape from STEP file")

        # Extract units and metadata
        units = _extract_step_units(file_path)

        # Try to get more detailed unit info from OCCT
        try:
            length_unit = Interface_Static.CVal("xstep.cascade.unit")
            if length_unit:
                units["length"] = str(length_unit)
        except Exception:
            pass

        metadata = {
            "nb_roots": nb_roots,
            "reader_type": "STEPControl_Reader",
            "file_size": file_path.stat().st_size,
        }

        # Get version info
        occt_version = getattr(version_module, "__version__", "unknown")

        return LoadedModel(
            model_id=file_path.stem,
            file_path=str(file_path),
            occt_shape=shape,
            units=units,
            metadata=metadata,
            occt_binding="pythonOCC",
            occt_version=occt_version,
        )

    except ImportError:
        logger.debug("pythonOCC not available")
        return None
    except Exception as e:
        logger.warning("pythonOCC import failed", file=str(file_path), error=str(e))
        return None


def _try_freecad_occ_import(file_path: Path) -> LoadedModel | None:
    """Attempt to load STEP file using FreeCAD OCC binding.

    Args:
        file_path: Path to STEP file

    Returns:
        LoadedModel if successful, None if failed
    """
    try:
        import OCC.Core
        from OCC.Core.IFSelect import IFSelect_RetDone
        from OCC.Core.Interface import Interface_Static
        from OCC.Core.STEPControl import STEPControl_Reader

        logger.debug("Attempting STEP import with FreeCAD OCC", file=str(file_path))

        # Create reader and configure
        reader = STEPControl_Reader()

        # Set some common options for better compatibility
        Interface_Static.SetCVal("xstep.cascade.unit", "mm")
        Interface_Static.SetRVal("read.precision.mode", 1)
        Interface_Static.SetRVal("read.precision.val", 0.01)

        # Read file
        status = reader.ReadFile(str(file_path))
        if status != IFSelect_RetDone:
            raise StepImportError(f"FreeCAD OCC read failed with status: {status}")

        # Transfer geometry
        nb_roots = reader.NbRootsForTransfer()
        if nb_roots == 0:
            raise StepImportError("No geometry roots found in STEP file")

        logger.debug("Found geometry roots", count=nb_roots)
        reader.TransferRoots()

        # Get the unified shape
        shape = reader.OneShape()
        if shape.IsNull():
            raise StepImportError("Failed to create unified shape from STEP file")

        # Extract units and metadata
        units = _extract_step_units(file_path)

        # Try to get more detailed unit info from OCCT
        try:
            length_unit = Interface_Static.CVal("xstep.cascade.unit")
            if length_unit:
                units["length"] = str(length_unit)
        except Exception:
            pass

        metadata = {
            "nb_roots": nb_roots,
            "reader_type": "STEPControl_Reader",
            "file_size": file_path.stat().st_size,
        }

        # Get version info - FreeCAD OCC may not have __version__
        occt_version = getattr(OCC.Core, "__version__", "freecad_bundled")

        return LoadedModel(
            model_id=file_path.stem,
            file_path=str(file_path),
            occt_shape=shape,
            units=units,
            metadata=metadata,
            occt_binding="freecad_occ",
            occt_version=occt_version,
        )

    except ImportError:
        logger.debug("FreeCAD OCC not available")
        return None
    except Exception as e:
        logger.warning("FreeCAD OCC import failed", file=str(file_path), error=str(e))
        return None


def load_step(file_path: str | Path) -> LoadedModel:
    """Load a STEP file using available OCCT bindings.

    This function attempts to load the STEP file using the available
    OCCT Python bindings in order of preference:
    1. pyOCCT (preferred)
    2. pythonOCC-core (fallback)
    3. FreeCAD OCC (fallback)

    Args:
        file_path: Path to the STEP file

    Returns:
        LoadedModel containing the geometry and metadata

    Raises:
        StepImportError: If file validation or import fails
        OCCTNotAvailableError: If no OCCT binding is available
    """
    # Validate file first
    validated_path = _validate_step_file(file_path)

    logger.info("Loading STEP file", file=str(validated_path))

    # Try each binding in order of preference
    loaders = [
        ("pyOCCT", _try_pyocct_import),
        ("pythonOCC", _try_pythonocc_import),
        ("freecad_occ", _try_freecad_occ_import),
    ]

    last_error = None
    for binding_name, loader_func in loaders:
        try:
            result = loader_func(validated_path)
            if result is not None:
                logger.info(
                    "Successfully loaded STEP file",
                    file=str(validated_path),
                    binding=binding_name,
                    model_id=result.model_id,
                    units=result.units,
                )
                return result
        except Exception as e:
            last_error = e
            logger.warning(
                "STEP import failed with binding",
                binding=binding_name,
                file=str(validated_path),
                error=str(e),
            )

    # If we get here, all loaders failed
    occt_info = get_occt_info()

    if (
        not occt_info["pyOCCT_available"]
        and not occt_info["pythonOCC_available"]
        and not occt_info["freecad_occ_available"]
    ):
        raise OCCTNotAvailableError(
            "No OCCT Python binding available. "
            "Please install pyOCCT (recommended) or pythonocc-core:\n"
            "  conda install -c conda-forge pythonocc-core\n"
            "  OR\n"
            "  pip install pythonocc-core"
        )

    # OCCT is available but import failed
    if last_error:
        raise StepImportError(f"Failed to load STEP file with available bindings: {last_error}")
    else:
        raise StepImportError("Failed to load STEP file: unknown error")
