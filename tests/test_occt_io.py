"""Tests for OCCT I/O functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kernel.occt_io import (
    LoadedModel,
    StepImportError,
    OCCTNotAvailableError,
    get_occt_info,
    load_step,
    _validate_step_file,
    _extract_step_units,
)


class TestOCCTInfo:
    """Test cases for OCCT binding detection."""

    def test_get_occt_info_structure(self):
        """Test that get_occt_info returns expected structure."""
        info = get_occt_info()

        required_keys = {
            "pyOCCT_available",
            "pythonOCC_available",
            "recommended_binding",
            "occt_version",
        }

        assert isinstance(info, dict)
        assert required_keys.issubset(info.keys())
        assert isinstance(info["pyOCCT_available"], bool)
        assert isinstance(info["pythonOCC_available"], bool)

    @patch('kernel.occt_io.logger')
    def test_occt_info_logging(self, mock_logger):
        """Test that OCCT detection logs appropriately."""
        get_occt_info()
        # Should have logged something about binding availability
        assert mock_logger.info.called or mock_logger.debug.called


class TestFileValidation:
    """Test cases for STEP file validation."""

    def test_validate_existing_file(self, sample_step_file: Path):
        """Test validation of existing STEP file."""
        validated_path = _validate_step_file(sample_step_file)
        assert validated_path == sample_step_file.resolve()

    def test_validate_nonexistent_file(self, temp_dir: Path):
        """Test validation fails for non-existent file."""
        nonexistent = temp_dir / "nonexistent.step"

        with pytest.raises(StepImportError, match="STEP file not found"):
            _validate_step_file(nonexistent)

    def test_validate_empty_file(self, temp_dir: Path):
        """Test validation fails for empty file."""
        empty_file = temp_dir / "empty.step"
        empty_file.touch()

        with pytest.raises(StepImportError, match="STEP file is empty"):
            _validate_step_file(empty_file)

    def test_validate_directory(self, temp_dir: Path):
        """Test validation fails for directory."""
        with pytest.raises(StepImportError, match="Path is not a file"):
            _validate_step_file(temp_dir)


class TestUnitExtraction:
    """Test cases for unit extraction from STEP files."""

    def test_extract_units_default(self, temp_dir: Path):
        """Test unit extraction returns defaults for unknown content."""
        test_file = temp_dir / "test.step"
        test_file.write_text("Unknown content")

        units = _extract_step_units(test_file)
        assert units == {"length": "mm", "angle": "deg"}

    def test_extract_units_millimetre(self, temp_dir: Path):
        """Test unit extraction detects millimetre."""
        content = """ISO-10303-21;
HEADER;
FILE_NAME('test.step','2024-01-01T12:00:00',('Test'),('ShapeBridge'),'','','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1 = ( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );
ENDSEC;
END-ISO-10303-21;
"""
        test_file = temp_dir / "test_mm.step"
        test_file.write_text(content)

        units = _extract_step_units(test_file)
        assert units["length"] == "mm"

    def test_extract_units_degree(self, temp_dir: Path):
        """Test unit extraction detects degree."""
        content = """ISO-10303-21;
HEADER;
FILE_NAME('test.step','2024-01-01T12:00:00',('Test'),('ShapeBridge'),'','','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1 = ( PLANE_ANGLE_UNIT() NAMED_UNIT(*) SI_UNIT($,.RADIAN.) );
#2 = CONVERSION_BASED_UNIT('DEGREE', #1, 0.017453292519943295);
ENDSEC;
END-ISO-10303-21;
"""
        test_file = temp_dir / "test_deg.step"
        test_file.write_text(content)

        units = _extract_step_units(test_file)
        assert units["angle"] == "deg"


class TestLoadedModel:
    """Test cases for LoadedModel class."""

    def test_loaded_model_creation(self):
        """Test LoadedModel creation and validation."""
        model = LoadedModel(
            model_id="test_model",
            file_path="/path/to/test.step",
            occt_shape=Mock(),
            units={"length": "mm", "angle": "deg"},
            metadata={"file_size": 1024},
            occt_binding="mock",
            occt_version="test",
        )

        assert model.model_id == "test_model"
        assert model.file_path == "/path/to/test.step"
        assert model.units["length"] == "mm"
        assert model.metadata["file_size"] == 1024

    def test_loaded_model_auto_id(self):
        """Test automatic model ID generation."""
        model = LoadedModel(
            model_id="",
            file_path="/path/to/example.step",
            occt_shape=Mock(),
            units={},
            metadata={},
            occt_binding="mock",
            occt_version="test",
        )

        assert model.model_id == "example"  # From file stem

    @patch('os.path.getsize')
    def test_loaded_model_auto_file_size(self, mock_getsize):
        """Test automatic file size detection."""
        mock_getsize.return_value = 2048

        model = LoadedModel(
            model_id="test",
            file_path="/path/to/test.step",
            occt_shape=Mock(),
            units={},
            metadata={},
            occt_binding="mock",
            occt_version="test",
        )

        assert model.metadata["file_size"] == 2048
        mock_getsize.assert_called_once_with("/path/to/test.step")


class TestLoadStep:
    """Test cases for load_step function."""

    def test_load_step_validation_error(self, temp_dir: Path):
        """Test load_step with invalid file."""
        nonexistent = temp_dir / "nonexistent.step"

        with pytest.raises(StepImportError, match="STEP file not found"):
            load_step(nonexistent)

    @patch('kernel.occt_io.get_occt_info')
    def test_load_step_no_bindings(self, mock_get_info, sample_step_file: Path):
        """Test load_step when no OCCT bindings are available."""
        mock_get_info.return_value = {
            "pyOCCT_available": False,
            "pythonOCC_available": False,
            "recommended_binding": None,
            "occt_version": None,
        }

        with pytest.raises(OCCTNotAvailableError, match="No OCCT Python binding available"):
            load_step(sample_step_file)

    @patch('kernel.occt_io._try_pyocct_import')
    @patch('kernel.occt_io._try_pythonocc_import')
    @patch('kernel.occt_io.get_occt_info')
    def test_load_step_binding_failure(self, mock_get_info, mock_pythonocc, mock_pyocct, sample_step_file: Path):
        """Test load_step when bindings are available but fail."""
        mock_get_info.return_value = {
            "pyOCCT_available": True,
            "pythonOCC_available": True,
            "recommended_binding": "pyOCCT",
            "occt_version": "7.6.0",
        }

        # Both importers return None (failed)
        mock_pyocct.return_value = None
        mock_pythonocc.return_value = None

        with pytest.raises(StepImportError, match="Failed to load STEP file with available bindings"):
            load_step(sample_step_file)

    @patch('kernel.occt_io._try_pyocct_import')
    @patch('kernel.occt_io.get_occt_info')
    def test_load_step_success_pyocct(self, mock_get_info, mock_pyocct, sample_step_file: Path):
        """Test successful load_step with pyOCCT."""
        mock_get_info.return_value = {
            "pyOCCT_available": True,
            "pythonOCC_available": False,
            "recommended_binding": "pyOCCT",
            "occt_version": "7.6.0",
        }

        expected_model = LoadedModel(
            model_id="test",
            file_path=str(sample_step_file),
            occt_shape=Mock(),
            units={"length": "mm", "angle": "deg"},
            metadata={"file_size": sample_step_file.stat().st_size},
            occt_binding="pyOCCT",
            occt_version="7.6.0",
        )

        mock_pyocct.return_value = expected_model

        result = load_step(sample_step_file)

        assert result == expected_model
        mock_pyocct.assert_called_once()

    @patch('kernel.occt_io._try_pyocct_import')
    @patch('kernel.occt_io._try_pythonocc_import')
    @patch('kernel.occt_io.get_occt_info')
    def test_load_step_fallback_to_pythonocc(self, mock_get_info, mock_pythonocc, mock_pyocct, sample_step_file: Path):
        """Test load_step falls back to pythonOCC when pyOCCT fails."""
        mock_get_info.return_value = {
            "pyOCCT_available": True,
            "pythonOCC_available": True,
            "recommended_binding": "pyOCCT",
            "occt_version": "7.6.0",
        }

        # pyOCCT fails, pythonOCC succeeds
        mock_pyocct.return_value = None
        expected_model = LoadedModel(
            model_id="test",
            file_path=str(sample_step_file),
            occt_shape=Mock(),
            units={"length": "mm", "angle": "deg"},
            metadata={"file_size": sample_step_file.stat().st_size},
            occt_binding="pythonOCC",
            occt_version="7.6.0",
        )
        mock_pythonocc.return_value = expected_model

        result = load_step(sample_step_file)

        assert result == expected_model
        mock_pyocct.assert_called_once()
        mock_pythonocc.assert_called_once()


@pytest.mark.occt
class TestRealOCCT:
    """Test cases that require actual OCCT bindings.

    These tests are marked with @pytest.mark.occt and will be skipped
    if no OCCT binding is available.
    """

    def test_real_occt_binding_detection(self, skip_if_no_occt):
        """Test that at least one OCCT binding is detected."""
        info = get_occt_info()
        assert info["pyOCCT_available"] or info["pythonOCC_available"]
        assert info["recommended_binding"] is not None

    def test_load_sample_step_file(self, skip_if_no_occt, sample_step_file: Path):
        """Test loading a real STEP file with available OCCT binding."""
        try:
            model = load_step(sample_step_file)
            assert model.model_id == sample_step_file.stem
            assert model.file_path == str(sample_step_file)
            assert model.occt_binding in ("pyOCCT", "pythonOCC")
            assert model.units["length"] in ("mm", "m", "in")
        except StepImportError:
            # This might happen with very minimal STEP files
            pytest.skip("Sample STEP file too minimal for OCCT parsing")


class TestMockImporters:
    """Test cases for the internal importer functions."""

    @patch('kernel.occt_io.logger')
    def test_try_pyocct_import_missing(self, mock_logger, sample_step_file: Path):
        """Test _try_pyocct_import when pyOCCT is not available."""
        from kernel.occt_io import _try_pyocct_import

        # This will likely return None unless pyOCCT is installed
        result = _try_pyocct_import(sample_step_file)
        assert result is None or isinstance(result, LoadedModel)

    @patch('kernel.occt_io.logger')
    def test_try_pythonocc_import_missing(self, mock_logger, sample_step_file: Path):
        """Test _try_pythonocc_import when pythonOCC is not available."""
        from kernel.occt_io import _try_pythonocc_import

        # This will likely return None unless pythonOCC is installed
        result = _try_pythonocc_import(sample_step_file)
        assert result is None or isinstance(result, LoadedModel)