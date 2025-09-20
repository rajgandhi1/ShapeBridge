"""Tests for MCP tools and session management."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from shapebridge_mcp.tools import (
    ShapeBridgeSession,
    SessionError,
    tool_load_step,
    tool_summarize_model,
    tool_export_view,
    tool_session_info,
    _session,
)
from kernel.occt_io import LoadedModel, StepImportError
from kernel.summary import GeometrySummary


class TestShapeBridgeSession:
    """Test cases for ShapeBridgeSession class."""

    def test_session_creation(self):
        """Test session creation with default settings."""
        session = ShapeBridgeSession()
        assert session._max_models == 10
        assert len(session._models) == 0
        assert len(session.list_models()) == 0

    def test_session_creation_with_limit(self):
        """Test session creation with custom model limit."""
        session = ShapeBridgeSession(max_models=5)
        assert session._max_models == 5

    def test_session_stats(self):
        """Test session statistics."""
        session = ShapeBridgeSession(max_models=5)
        stats = session.get_session_stats()

        assert stats["loaded_models"] == 0
        assert stats["max_models"] == 5
        assert stats["model_ids"] == []

    def test_has_model(self):
        """Test model existence checking."""
        session = ShapeBridgeSession()

        # Add a mock model directly
        mock_model = Mock(spec=LoadedModel)
        mock_model.model_id = "test_model"
        session._models["test_model"] = mock_model

        assert session.has_model("test_model")
        assert not session.has_model("nonexistent")

    def test_get_model(self):
        """Test model retrieval."""
        session = ShapeBridgeSession()

        mock_model = Mock(spec=LoadedModel)
        session._models["test_model"] = mock_model

        retrieved = session.get_model("test_model")
        assert retrieved is mock_model

        not_found = session.get_model("nonexistent")
        assert not_found is None

    def test_remove_model(self):
        """Test model removal."""
        session = ShapeBridgeSession()

        # Add mock data
        mock_model = Mock(spec=LoadedModel)
        mock_summary = Mock(spec=GeometrySummary)
        session._models["test_model"] = mock_model
        session._summaries["test_model"] = mock_summary
        session._load_times["test_model"] = 123.456

        # Remove model
        session.remove_model("test_model")

        assert not session.has_model("test_model")
        assert session.get_summary("test_model") is None
        assert "test_model" not in session._load_times

        # Removing non-existent model should not error
        session.remove_model("nonexistent")

    def test_cleanup_old_models(self):
        """Test automatic cleanup of old models."""
        session = ShapeBridgeSession(max_models=2)

        # Add models with different load times
        for i in range(3):
            model_id = f"model_{i}"
            mock_model = Mock(spec=LoadedModel)
            mock_model.model_id = model_id
            session._models[model_id] = mock_model
            session._load_times[model_id] = i  # model_0 is oldest

        session.cleanup_old_models()

        # Should keep only 2 newest models
        assert len(session._models) == 2
        assert "model_0" not in session._models  # Oldest removed
        assert "model_1" in session._models
        assert "model_2" in session._models

    @patch('shapebridge_mcp.tools.load_step')
    def test_load_model_success(self, mock_load_step):
        """Test successful model loading."""
        session = ShapeBridgeSession()

        mock_model = Mock(spec=LoadedModel)
        mock_model.model_id = "test_model"
        mock_model.file_path = "/path/to/test.step"
        mock_model.units = {"length": "mm"}
        mock_model.occt_binding = "pyOCCT"
        mock_load_step.return_value = mock_model

        result = session.load_model("/path/to/test.step")

        assert result is mock_model
        assert session.has_model("test_model")
        assert "test_model" in session._load_times
        mock_load_step.assert_called_once_with("/path/to/test.step")

    @patch('shapebridge_mcp.tools.load_step')
    def test_load_model_failure(self, mock_load_step):
        """Test model loading failure."""
        session = ShapeBridgeSession()

        mock_load_step.side_effect = StepImportError("Test error")

        with pytest.raises(SessionError, match="Failed to load STEP file"):
            session.load_model("/path/to/test.step")

        assert len(session._models) == 0

    @patch('shapebridge_mcp.tools.summarize_shape')
    def test_generate_summary_success(self, mock_summarize_shape):
        """Test successful summary generation."""
        session = ShapeBridgeSession()

        # Add mock model
        mock_model = Mock(spec=LoadedModel)
        session._models["test_model"] = mock_model

        # Mock summary
        mock_summary = Mock(spec=GeometrySummary)
        mock_summary.faces = 6
        mock_summary.edges = 12
        mock_summary.vertices = 8
        mock_summarize_shape.return_value = mock_summary

        result = session.generate_summary("test_model")

        assert result is mock_summary
        assert session.get_summary("test_model") is mock_summary
        mock_summarize_shape.assert_called_once_with(mock_model)

    def test_generate_summary_no_model(self):
        """Test summary generation for non-existent model."""
        session = ShapeBridgeSession()

        with pytest.raises(SessionError, match="Model not found in session"):
            session.generate_summary("nonexistent")

    @patch('shapebridge_mcp.tools.summarize_shape')
    @patch('shapebridge_mcp.tools.create_placeholder_summary')
    def test_generate_summary_failure(self, mock_placeholder, mock_summarize_shape):
        """Test summary generation failure handling."""
        session = ShapeBridgeSession()

        # Add mock model
        mock_model = Mock(spec=LoadedModel)
        session._models["test_model"] = mock_model

        # Mock analysis failure
        mock_summarize_shape.side_effect = Exception("Analysis failed")

        mock_placeholder_summary = Mock(spec=GeometrySummary)
        mock_placeholder.return_value = mock_placeholder_summary

        result = session.generate_summary("test_model")

        assert result is mock_placeholder_summary
        mock_placeholder.assert_called_once_with("test_model", "Analysis failed")

    @patch('shapebridge_mcp.tools.export_model_view')
    def test_export_view_success(self, mock_export):
        """Test successful view export."""
        session = ShapeBridgeSession()

        # Add mock model
        mock_model = Mock(spec=LoadedModel)
        session._models["test_model"] = mock_model

        expected_result = {
            "format": "glb",
            "uri": "memory://test_model.glb",
            "size_bytes": 1024,
        }
        mock_export.return_value = expected_result

        result = session.export_view("test_model", "glb")

        assert result == expected_result
        mock_export.assert_called_once_with(mock_model, format="glb")

    def test_export_view_no_model(self):
        """Test view export for non-existent model."""
        session = ShapeBridgeSession()

        with pytest.raises(SessionError, match="Model not found in session"):
            session.export_view("nonexistent")


class TestMCPTools:
    """Test cases for MCP tool functions."""

    def test_tool_load_step_missing_path(self):
        """Test load_step tool with missing path parameter."""
        with pytest.raises(ValueError, match="Missing required parameter: path"):
            tool_load_step({})

    def test_tool_load_step_empty_path(self):
        """Test load_step tool with empty path."""
        with pytest.raises(ValueError, match="Parameter 'path' cannot be empty"):
            tool_load_step({"path": ""})

    def test_tool_load_step_nonexistent_file(self, temp_dir: Path):
        """Test load_step tool with non-existent file."""
        nonexistent = temp_dir / "nonexistent.step"

        with pytest.raises(ValueError, match="File not found"):
            tool_load_step({"path": str(nonexistent)})

    @patch('shapebridge_mcp.tools._session')
    def test_tool_load_step_success(self, mock_session, sample_step_file: Path):
        """Test successful load_step tool execution."""
        mock_model = Mock(spec=LoadedModel)
        mock_model.model_id = "test"
        mock_model.file_path = str(sample_step_file)
        mock_model.units = {"length": "mm"}
        mock_model.occt_binding = "pyOCCT"
        mock_model.occt_version = "7.6.0"
        mock_model.metadata = {"file_size": 1024}

        mock_session.load_model.return_value = mock_model
        mock_session.get_session_stats.return_value = {"loaded_models": 1}

        result = tool_load_step({"path": str(sample_step_file)})

        assert result["success"] is True
        assert result["model_id"] == "test"
        assert result["units"]["length"] == "mm"
        mock_session.load_model.assert_called_once_with(str(sample_step_file))

    @patch('shapebridge_mcp.tools._session')
    def test_tool_load_step_session_error(self, mock_session, sample_step_file: Path):
        """Test load_step tool with session error."""
        mock_session.load_model.side_effect = SessionError("Test error")

        result = tool_load_step({"path": str(sample_step_file)})

        assert result["success"] is False
        assert "Test error" in result["error"]
        assert result["model_id"] is None

    def test_tool_summarize_model_missing_id(self):
        """Test summarize_model tool with missing model_id."""
        with pytest.raises(ValueError, match="Missing required parameter: model_id"):
            tool_summarize_model({})

    def test_tool_summarize_model_empty_id(self):
        """Test summarize_model tool with empty model_id."""
        with pytest.raises(ValueError, match="Parameter 'model_id' cannot be empty"):
            tool_summarize_model({"model_id": ""})

    @patch('shapebridge_mcp.tools._session')
    @patch('shapebridge_mcp.tools.dump_jsonl')
    def test_tool_summarize_model_success(self, mock_dump, mock_session, temp_dir: Path):
        """Test successful summarize_model tool execution."""
        # Mock summary
        mock_summary = Mock(spec=GeometrySummary)
        mock_summary.units = {"length": "mm", "angle": "deg"}
        mock_summary.solids = 1
        mock_summary.faces = 6
        mock_summary.edges = 12
        mock_summary.vertices = 8
        mock_summary.bounding_box = {"min_x": 0, "max_x": 10}
        mock_summary.surface_area = 600.0
        mock_summary.volume = 1000.0
        mock_summary.has_pmi = False
        mock_summary.has_surfaces = True
        mock_summary.file_size = 1024
        mock_summary.occt_binding = "pyOCCT"
        mock_summary.analysis_warnings = []

        mock_session.generate_summary.return_value = mock_summary

        result = tool_summarize_model({"model_id": "test_model", "out_dir": str(temp_dir)})

        assert result["success"] is True
        assert result["model_id"] == "test_model"
        assert result["summary"]["topology"]["faces"] == 6
        assert result["ir_valid"] is True
        assert str(temp_dir) in result["ir_path"]

        mock_session.generate_summary.assert_called_once_with("test_model")
        mock_dump.assert_called_once()

    def test_tool_export_view_missing_id(self):
        """Test export_view tool with missing model_id."""
        with pytest.raises(ValueError, match="Missing required parameter: model_id"):
            tool_export_view({})

    def test_tool_export_view_invalid_format(self):
        """Test export_view tool with invalid format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            tool_export_view({"model_id": "test", "format": "invalid"})

    @patch('shapebridge_mcp.tools._session')
    def test_tool_export_view_success(self, mock_session):
        """Test successful export_view tool execution."""
        expected_result = {
            "format": "glb",
            "uri": "memory://test.glb",
            "mime_type": "model/gltf-binary",
            "size_bytes": 1024,
            "data_base64": "dGVzdA==",
        }

        mock_session.export_view.return_value = expected_result

        result = tool_export_view({"model_id": "test_model", "format": "glb"})

        assert result["success"] is True
        assert result["format"] == "glb"
        assert result["uri"] == "memory://test.glb"
        mock_session.export_view.assert_called_once_with("test_model", format="glb")

    @patch('shapebridge_mcp.tools._session')
    def test_tool_session_info(self, mock_session):
        """Test session_info tool."""
        mock_session.get_session_stats.return_value = {
            "loaded_models": 2,
            "max_models": 10,
            "model_ids": ["model1", "model2"],
        }

        # Mock models
        mock_model1 = Mock(spec=LoadedModel)
        mock_model1.file_path = "/path/to/model1.step"
        mock_model1.units = {"length": "mm"}
        mock_model1.occt_binding = "pyOCCT"

        mock_summary1 = Mock(spec=GeometrySummary)
        mock_summary1.faces = 6

        mock_session.get_model.side_effect = lambda mid: mock_model1 if mid == "model1" else None
        mock_session.get_summary.side_effect = lambda mid: mock_summary1 if mid == "model1" else None

        result = tool_session_info()

        assert result["success"] is True
        assert result["session_stats"]["loaded_models"] == 2
        assert len(result["models"]) == 2
        assert "available_tools" in result

        model1_detail = next(m for m in result["models"] if m["model_id"] == "model1")
        assert model1_detail["has_summary"] is True
        assert model1_detail["topology"]["faces"] == 6


class TestGlobalSession:
    """Test cases for global session behavior."""

    def test_global_session_exists(self):
        """Test that global session is properly initialized."""
        assert _session is not None
        assert isinstance(_session, ShapeBridgeSession)

    def test_global_session_persistent(self):
        """Test that global session persists across tool calls."""
        # This is more of an integration test to ensure the global session
        # maintains state across different MCP tool invocations
        initial_stats = _session.get_session_stats()
        assert isinstance(initial_stats, dict)
        assert "loaded_models" in initial_stats