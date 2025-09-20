"""Pytest configuration and shared fixtures.

Provides common test fixtures and configuration for the ShapeBridge test suite.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import pytest
import structlog

from kernel.occt_io import LoadedModel, get_occt_info
from stepgraph_ir.schema import IR, Node, Edge, create_part_node


# Configure test logging
structlog.configure(
    processors=[
        structlog.testing.LogCapture(),
    ],
    logger_factory=structlog.testing.TestingLoggerFactory(),
    cache_logger_on_first_use=True,
)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_step_content() -> str:
    """Provide minimal valid STEP file content for testing."""
    return """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Test file for ShapeBridge'),'2;1');
FILE_NAME('test.step','2024-01-01T12:00:00',('Test'),('ShapeBridge'),'','','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1 = CARTESIAN_POINT('',($,0.,0.));
#2 = CARTESIAN_POINT('',(1.,0.,0.));
#3 = CARTESIAN_POINT('',(1.,1.,0.));
#4 = CARTESIAN_POINT('',(0.,1.,0.));
ENDSEC;
END-ISO-10303-21;
"""


@pytest.fixture
def sample_step_file(temp_dir: Path, sample_step_content: str) -> Path:
    """Create a sample STEP file for testing."""
    step_file = temp_dir / "test.step"
    step_file.write_text(sample_step_content, encoding="utf-8")
    return step_file


@pytest.fixture
def mock_loaded_model() -> LoadedModel:
    """Provide a mock LoadedModel for testing."""
    return LoadedModel(
        model_id="test_model",
        file_path="/path/to/test.step",
        occt_shape=None,  # Mock shape object
        units={"length": "mm", "angle": "deg"},
        metadata={"file_size": 1024, "nb_roots": 1},
        occt_binding="mock",
        occt_version="test",
    )


@pytest.fixture
def sample_ir() -> IR:
    """Provide a sample IR for testing."""
    part_node = create_part_node("test_part", "test_part_id")
    part_node.attrs["topology"] = {"faces": 6, "edges": 12, "vertices": 8}

    return IR(
        model_id="test_model",
        nodes=[part_node],
        edges=[],
        units={"length": "mm", "angle": "deg"},
        provenance={"phase": "0", "generator": "test"},
    )


@pytest.fixture
def skip_if_no_occt():
    """Skip test if no OCCT binding is available."""
    occt_info = get_occt_info()
    if not occt_info["pyOCCT_available"] and not occt_info["pythonOCC_available"]:
        pytest.skip("No OCCT binding available (pyOCCT or pythonOCC required)")


class MockShape:
    """Mock OCCT shape for testing."""

    def __init__(self, is_null: bool = False):
        self._is_null = is_null

    def IsNull(self) -> bool:
        return self._is_null


@pytest.fixture
def mock_occt_shape() -> MockShape:
    """Provide a mock OCCT shape for testing."""
    return MockShape(is_null=False)


@pytest.fixture
def mock_null_shape() -> MockShape:
    """Provide a mock null OCCT shape for testing."""
    return MockShape(is_null=True)