# ShapeBridge Phase 0

**Status:** Phase 0 (Foundations: IR + MCP skeleton, no ML)

ShapeBridge is a deterministic STEP→IR pipeline with MCP server integration for Claude Code/Desktop.

## Quick Start

### Prerequisites

- **Python 3.10-3.12** (3.11 recommended)
- **Conda** (for OCCT bindings)
- **Git**

### Installation

#### Method 1: Conda Environment (Recommended)

```bash
# Clone repository
git clone <your-repo-url> && cd shapebridge

# Create conda environment with Python 3.11
conda create --name shapebridge python=3.11 -y

# Activate environment
conda activate shapebridge

# Install OCCT bindings
conda install -c conda-forge pythonocc-core -y

# Install ShapeBridge in development mode
pip install -e ".[dev]"

# Setup pre-commit hooks
pre-commit install
```
### Verification

```bash
# Activate environment (if not already active)
conda activate shapebridge

# Check installation
shapebridge info

# Test with sample file
shapebridge load tests/data/samples/minimal.step
shapebridge summarize tests/data/samples/minimal.step --out test.jsonl
```

### Usage

**CLI:**
```bash
# Activate environment first
conda activate shapebridge

# Load and analyze STEP files
shapebridge info                              # Check system status
shapebridge load /path/to/model.step         # Load and validate STEP file
shapebridge summarize /path/to/model.step    # Generate IR summary
shapebridge export /path/to/model.step       # Export 3D view (Phase 0: placeholder)
```

**MCP Server (Claude Code integration):**
```bash
# Activate environment and start server
conda activate shapebridge
shapebridge-mcp

# Available MCP tools:
# - load_step(path: str) -> dict
# - summarize_model(model_id: str, out_dir: str | None) -> dict
# - export_view(model_id: str, format: str = "glb") -> dict
# - session_info() -> dict
```

**Example Claude Code workflow:**
```python
# Load a STEP file
result = load_step("/path/to/bracket.step")
print(f"Loaded: {result['model_id']}")

# Generate summary and IR
summary = summarize_model(result['model_id'], "/tmp")
print(f"Faces: {summary['summary']['topology']['faces']}")

# Export 3D view
view = export_view(result['model_id'], "glb")
print(f"3D model: {view['uri']}")
```

## Phase 0 Scope

✅ STEP ingestion via Open CASCADE
✅ Deterministic STEPGraph-IR generation
✅ MCP server with core tools
✅ GLB/GLTF export (placeholder)
❌ ML features, feature recognition (Phase 1+)

## Development

### Environment Setup

```bash
# Activate development environment
conda activate shapebridge
```

### Development Commands

```bash
# Quality checks
make lint      # Ruff linting
make fmt       # Format code with ruff and black
make type      # MyPy type checking
make test      # Run pytest
make test-cov  # Run tests with coverage

# Development workflow
make dev       # Format + lint + type + test
make clean     # Clean temporary files

# Server and tools
make mcp       # Start MCP server
make run       # Run CLI help
```

### Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m "not occt"        # Skip OCCT-dependent tests
pytest -m "integration"     # Integration tests only
pytest tests/test_ir_schema.py -v  # Specific test file

# Run with coverage
pytest --cov=src --cov-report=html
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SHAPEBRIDGE_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `SHAPEBRIDGE_MAX_MODELS` | `10` | Max models in MCP session |
| `SHAPEBRIDGE_CACHE_DIR` | `/tmp` | Temporary file location |

### Troubleshooting

**"No OCCT binding available":**
- Ensure conda environment is activated: 'conda activate shapebridge'
- Reinstall OCCT: `conda install -c conda-forge pythonocc-core -y`
- Check Python path doesn't conflict with other installations

**Import errors:**
- Verify environment: `conda list | grep pythonocc`
- Clean and reinstall: `pip install -e ".[dev]" --force-reinstall`

## Quick Reference

### First Time Setup
```bash
git clone <repo-url> && cd shapebridge
conda create --name shapebridge python=3.11 -y
conda activate shapebridge
conda install -c conda-forge pythonocc-core -y
pip install -e ".[dev]"
pre-commit install
```

### Key Files
- `src/shapebridge_mcp/server.py` - MCP server for Claude Code
- `src/kernel/occt_io.py` - STEP file loading
- `tests/data/samples/` - Sample STEP files for testing

## Architecture

- `src/stepgraph_ir/` - IR schema and serialization
- `src/kernel/` - OCCT integration and geometry ops
- `src/shapebridge_mcp/` - MCP server and tools
- `src/shapebridge/` - CLI utilities
- `tests/` - Test suite with sample STEP files

## Documentation

- **[Setup Guide](docs/SETUP.md)** - Detailed installation instructions
- **[IR Specification](docs/IR_SPEC.md)** - STEPGraph-IR format details
- **[Development Phases](docs/PHASES.md)** - Project roadmap and phases
- **[Contributing](CONTRIBUTING.md)** - Development guidelines

## License

Apache-2.0
