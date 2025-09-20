# Contributing to ShapeBridge

Welcome to ShapeBridge! We appreciate your interest in contributing to the project. This guide will help you get started with development and understand our processes.

## Development Environment Setup

### Prerequisites
- Python 3.10 or higher
- Git
- An OCCT Python binding (pyOCCT or pythonocc-core)

### Quick Setup
```bash
# Fork and clone the repository
git clone https://github.com/yourusername/shapebridge.git
cd shapebridge

# Set up development environment
make setup

# Run tests to verify setup
make test
```

### Detailed Setup
1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
4. **Install in development mode**:
   ```bash
   pip install -e .[dev]
   ```
5. **Install OCCT binding** (see [SETUP.md](docs/SETUP.md))
6. **Set up pre-commit hooks**:
   ```bash
   pre-commit install
   ```

## Development Workflow

### Branch Strategy
- `main` - Stable releases and hotfixes
- `develop` - Integration branch for new features
- `feature/feature-name` - New feature development
- `bugfix/issue-description` - Bug fixes
- `docs/documentation-update` - Documentation changes

### Making Changes

1. **Create a feature branch**:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following our coding standards

3. **Test your changes**:
   ```bash
   make test        # Run all tests
   make lint        # Check code style
   make type        # Run type checker
   ```

4. **Commit with conventional commits**:
   ```bash
   git commit -m "feat: add geometric constraint validation"
   git commit -m "fix: resolve memory leak in OCCT loader"
   git commit -m "docs: update IR specification"
   ```

5. **Push and create a pull request**:
   ```bash
   git push origin feature/your-feature-name
   ```

### Conventional Commits

We use conventional commits for clear release notes:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

## Code Standards

### Python Style
- **Line length**: 100 characters
- **Formatter**: Black + Ruff
- **Imports**: Sorted with isort
- **Type hints**: Required for all public functions
- **Docstrings**: Google style

### Example Code Style
```python
"""Module for STEP file processing."""

from __future__ import annotations

from typing import Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


def process_step_file(
    file_path: str,
    units: Optional[Dict[str, str]] = None
) -> List[GeometricEntity]:
    """Process a STEP file and extract geometric entities.

    Args:
        file_path: Path to the STEP file
        units: Optional unit overrides

    Returns:
        List of extracted geometric entities

    Raises:
        StepImportError: If file processing fails
    """
    logger.info("Processing STEP file", path=file_path)

    if units is None:
        units = {"length": "mm", "angle": "deg"}

    # Implementation here...
```

### Testing Standards
- **Coverage**: Aim for >90% test coverage
- **Test types**: Unit tests, integration tests, property-based tests
- **Naming**: `test_function_name_condition_expected_result`
- **Fixtures**: Use pytest fixtures for complex setup
- **Mocking**: Mock external dependencies (OCCT, file system)

### Example Test
```python
def test_load_step_file_success_returns_loaded_model(sample_step_file):
    """Test that load_step successfully loads a valid STEP file."""
    # Arrange
    expected_model_id = "test_model"

    # Act
    result = load_step(sample_step_file)

    # Assert
    assert result.model_id == expected_model_id
    assert result.occt_binding in ("pyOCCT", "pythonOCC")
    assert "length" in result.units
```

## Architecture Guidelines

### Module Organization
```
src/
├── shapebridge/          # CLI and main interfaces
├── stepgraph_ir/         # IR schema and serialization
├── kernel/               # Core OCCT integration
└── shapebridge_mcp/      # MCP server implementation
```

### Design Principles

1. **Separation of Concerns**
   - IR schema independent of OCCT
   - MCP server separate from core logic
   - CLI tools as thin wrappers

2. **Error Handling**
   - Use custom exceptions for domain errors
   - Provide clear error messages
   - Log errors with structured context

3. **Performance**
   - Lazy loading where possible
   - Memory-conscious for large models
   - Deterministic algorithms

4. **Extensibility**
   - Plugin architecture for analyzers
   - Version-aware serialization
   - Forward-compatible IR schema

### Adding New Features

#### New Node Types
1. Add to `NodeType` enum in `schema.py`
2. Update sorting priorities in `serialize.py`
3. Add factory function if needed
4. Write comprehensive tests
5. Update documentation

#### New MCP Tools
1. Implement tool function in `tools.py`
2. Add FastMCP endpoint in `server.py`
3. Add comprehensive error handling
4. Write integration tests
5. Update API documentation

#### New Analysis Capabilities
1. Add to appropriate kernel module
2. Ensure deterministic output
3. Handle missing OCCT gracefully
4. Add to IR schema if needed
5. Write performance tests

## Testing

### Running Tests
```bash
# All tests
make test

# Specific test categories
pytest -m "not occt"        # Without OCCT dependencies
pytest -m "integration"     # Integration tests only
pytest -m "slow"            # Performance tests

# With coverage
make test-cov

# Specific test file
pytest tests/test_ir_schema.py -v
```

### Writing Tests

#### Unit Tests
Focus on individual functions with mocked dependencies:

```python
@patch('kernel.occt_io.load_step')
def test_session_load_model_success(mock_load_step):
    # Arrange
    mock_model = Mock(spec=LoadedModel)
    mock_load_step.return_value = mock_model
    session = ShapeBridgeSession()

    # Act
    result = session.load_model("/path/to/test.step")

    # Assert
    assert result is mock_model
    mock_load_step.assert_called_once()
```

#### Integration Tests
Test complete workflows with real components:

```python
def test_complete_step_to_ir_workflow(sample_step_file, temp_dir):
    """Test complete workflow from STEP file to IR."""
    # Load model
    loaded_model = load_step(sample_step_file)

    # Generate summary
    summary = summarize_shape(loaded_model)

    # Create IR
    ir = create_ir_from_summary(loaded_model.model_id, summary)

    # Serialize and verify
    output_path = temp_dir / "test.jsonl"
    dump_jsonl(ir, output_path)

    loaded_ir = list(load_jsonl(output_path))[0]
    assert loaded_ir.model_id == loaded_model.model_id
```

#### Property-Based Tests
Use hypothesis for edge cases:

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1), st.integers(min_value=0))
def test_node_creation_with_random_data(node_id, face_count):
    """Test node creation with various inputs."""
    node = Node(id=node_id, type="Part")
    node.attrs["topology"] = {"faces": face_count}

    assert node.id == node_id
    assert node.attrs["topology"]["faces"] == face_count
```

### Test Fixtures
Use comprehensive fixtures in `conftest.py`:

```python
@pytest.fixture
def loaded_model_with_geometry():
    """Provide a loaded model with realistic geometry data."""
    return LoadedModel(
        model_id="test_geometry",
        file_path="/test/path.step",
        occt_shape=MockShape(),
        units={"length": "mm", "angle": "deg"},
        metadata={"faces": 6, "edges": 12, "vertices": 8},
        occt_binding="mock",
        occt_version="test"
    )
```

## Documentation

### Types of Documentation

1. **API Documentation** - Docstrings in code
2. **User Guides** - How to use ShapeBridge
3. **Developer Guides** - Architecture and development
4. **Specifications** - Formal specifications (IR, etc.)

### Writing Documentation

#### Docstrings
Use Google style with type information:

```python
def analyze_geometry(shape: Any, precision: float = 0.01) -> GeometryAnalysis:
    """Analyze geometric properties of a shape.

    Computes topological information, surface area, volume, and other
    geometric properties using Open CASCADE algorithms.

    Args:
        shape: OCCT TopoDS_Shape to analyze
        precision: Analysis precision for tessellation

    Returns:
        GeometryAnalysis containing computed properties

    Raises:
        AnalysisError: If geometry analysis fails
        ValueError: If precision is not positive

    Example:
        >>> analysis = analyze_geometry(my_shape, precision=0.001)
        >>> print(f"Volume: {analysis.volume} mm³")
    """
```

#### User Documentation
- Focus on practical examples
- Include common use cases
- Provide troubleshooting guides
- Keep up to date with code changes

#### Technical Specifications
- Be precise and unambiguous
- Include version information
- Provide migration guides
- Use formal schemas where appropriate

## Release Process

### Version Numbering
We use semantic versioning:
- `MAJOR.MINOR.PATCH`
- `MAJOR` - Breaking changes
- `MINOR` - New features, backward compatible
- `PATCH` - Bug fixes, backward compatible

### Release Checklist
1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Update documentation
5. Create release PR to `main`
6. Tag release after merge
7. Create GitHub release
8. Publish to PyPI (if applicable)

## Getting Help

### Community
- **GitHub Issues** - Bug reports and feature requests
- **GitHub Discussions** - General questions and ideas
- **Discord** - Real-time chat (link in README)

### Development Questions
- Check existing issues and PRs
- Ask in GitHub Discussions
- Ping maintainers on Discord
- Schedule office hours if needed

### Reporting Bugs
Use the bug report template with:
1. **Environment details** (OS, Python version, OCCT binding)
2. **Steps to reproduce** (minimal example preferred)
3. **Expected vs actual behavior**
4. **Relevant logs** (with `SHAPEBRIDGE_LOG_LEVEL=DEBUG`)
5. **Sample files** (if applicable and non-proprietary)

## Code Review Process

### Submitting PRs
1. **Clear description** of changes and motivation
2. **Link to related issues**
3. **Test coverage** for new functionality
4. **Documentation updates** if needed
5. **Conventional commit** messages

### Review Criteria
- Code quality and style
- Test coverage and quality
- Documentation completeness
- Performance impact
- Backward compatibility
- Security considerations

### Review Process
1. Automated checks (CI, pre-commit)
2. Core team review
3. Community feedback welcome
4. Address review comments
5. Final approval and merge

## Phase-Specific Contributions

### Phase 0 (Current)
Focus on stability and completeness:
- Bug fixes and edge cases
- Documentation improvements
- Test coverage gaps
- Performance optimizations
- Platform compatibility

### Phase 1 (Upcoming)
Real geometry processing:
- Tessellation implementation
- Advanced geometry analysis
- Feature recognition
- Assembly handling
- PMI extraction

### Future Phases
- Constraint solving (Phase 2)
- Machine learning integration (Phase 3)
- Distributed processing (Phase 4)

## Recognition

Contributors are recognized through:
- `CONTRIBUTORS.md` file
- GitHub contributor graphs
- Release notes acknowledgments
- Community highlights

We welcome contributions of all types:
- Code (features, fixes, tests)
- Documentation (guides, tutorials, API docs)
- Issue reports and reproduction
- Community support and discussions
- Performance testing and benchmarking

Thank you for contributing to ShapeBridge! 🚀