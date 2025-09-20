# ShapeBridge Setup Guide

This guide covers installation and setup of ShapeBridge for different use cases and platforms.

## Quick Start

### Prerequisites
- Python 3.10 or higher
- One of: pyOCCT or pythonocc-core (see [OCCT Installation](#occt-installation))

### Basic Installation
```bash
# Clone repository
git clone https://github.com/eicon-vision/shapebridge.git
cd shapebridge

# Install ShapeBridge
pip install -e .

# Verify installation
shapebridge info
```

## OCCT Installation

ShapeBridge requires Open CASCADE Technology (OCCT) Python bindings. Choose one:

### Option 1: pyOCCT (Recommended)
```bash
# Using conda (recommended)
conda install -c conda-forge pythonocc-core

# Verify
python -c "import OCCT; print('pyOCCT available')"
```

### Option 2: pythonOCC-core
```bash
# Using pip
pip install pythonocc-core

# Verify
python -c "import OCP; print('pythonOCC available')"
```

### Platform-Specific Instructions

#### Ubuntu/Debian
```bash
# System dependencies
sudo apt-get update
sudo apt-get install -y \
    libgl1-mesa-glx \
    libglu1-mesa \
    libxrender1 \
    libxext6 \
    libsm6 \
    libxrandr2

# Install OCCT binding
conda install -c conda-forge pythonocc-core
```

#### macOS
```bash
# Using conda (recommended)
conda install -c conda-forge pythonocc-core

# Or using homebrew + pip
brew install opencascade
pip install pythonocc-core
```

#### Windows
```bash
# Using conda (recommended)
conda install -c conda-forge pythonocc-core

# Alternative: Download pre-built wheels
pip install pythonocc-core
```

### Troubleshooting OCCT Installation

#### ImportError: No module named 'OCCT'
```bash
# Check Python environment
python -c "import sys; print(sys.path)"

# Reinstall with explicit channels
conda install -c conda-forge -c dlr-sc pythonocc-core
```

#### Library Loading Issues (Linux)
```bash
# Add to ~/.bashrc or equivalent
export LD_LIBRARY_PATH=/path/to/opencascade/lib:$LD_LIBRARY_PATH

# Or use conda environment activation
conda activate shapebridge_env
```

#### Permission Issues (macOS)
```bash
# Fix library permissions
sudo xattr -r -d com.apple.quarantine /path/to/conda/envs/*/lib
```

## Development Setup

### Full Development Environment
```bash
# Clone and enter directory
git clone https://github.com/eicon-vision/shapebridge.git
cd shapebridge

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install with development dependencies
pip install -e .[dev]

# Install OCCT binding
conda install -c conda-forge pythonocc-core

# Setup pre-commit hooks
pre-commit install

# Verify installation
make setup
make test
```

### IDE Configuration

#### VS Code
```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"]
}
```

#### PyCharm
1. File → Settings → Project → Python Interpreter
2. Add interpreter from `./venv/bin/python`
3. Enable pytest as test runner
4. Configure ruff as external tool

## Claude Code Integration

### MCP Server Setup

#### 1. Install ShapeBridge with MCP Support
```bash
pip install -e .
shapebridge-mcp  # Test MCP server
```

#### 2. Configure Claude Desktop

Add to Claude Desktop settings:
```json
{
  "mcpServers": {
    "shapebridge": {
      "command": "shapebridge-mcp",
      "args": []
    }
  }
}
```

#### 3. Test Integration
```bash
# Start MCP server (stdio mode)
shapebridge-mcp

# In Claude Code, test with:
load_step("/path/to/your/model.step")
```

### Available MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `load_step` | Load STEP file | `path: str` |
| `summarize_model` | Generate IR summary | `model_id: str, out_dir?: str` |
| `export_view` | Export 3D view | `model_id: str, format?: str` |
| `session_info` | Get session info | (none) |

### Example Workflow
```python
# In Claude Code:
result = load_step("/path/to/bracket.step")
model_id = result["model_id"]

summary = summarize_model(model_id, "/tmp")
print(f"Part has {summary['summary']['topology']['faces']} faces")

export = export_view(model_id, "glb")
print(f"3D model: {export['uri']}")
```

## Docker Setup

### Basic Container
```dockerfile
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*

# Install ShapeBridge
COPY . /app
WORKDIR /app
RUN pip install -e .

# Install OCCT (requires conda in container)
RUN pip install pythonocc-core

EXPOSE 8080
CMD ["shapebridge-mcp"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  shapebridge:
    build: .
    volumes:
      - ./data:/data
    environment:
      - PYTHONPATH=/app
    command: shapebridge-mcp
```

## Production Deployment

### Systemd Service (Linux)
```ini
# /etc/systemd/system/shapebridge-mcp.service
[Unit]
Description=ShapeBridge MCP Server
After=network.target

[Service]
Type=simple
User=shapebridge
WorkingDirectory=/opt/shapebridge
ExecStart=/opt/shapebridge/venv/bin/shapebridge-mcp
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Process Management
```bash
# Enable service
sudo systemctl enable shapebridge-mcp
sudo systemctl start shapebridge-mcp

# Monitor
sudo systemctl status shapebridge-mcp
sudo journalctl -f -u shapebridge-mcp
```

## Performance Tuning

### Memory Management
```bash
# Set session limits for MCP server
export SHAPEBRIDGE_MAX_MODELS=20
export SHAPEBRIDGE_MEMORY_LIMIT=2GB
```

### Parallel Processing
```python
# In your code
import os
os.environ['OMP_NUM_THREADS'] = '4'  # Control OCCT threading
```

### File System Optimization
```bash
# Use SSD for temporary files
export TMPDIR=/fast/ssd/temp

# Optimize for large STEP files
ulimit -n 4096  # Increase file descriptor limit
```

## Testing Setup

### Run Full Test Suite
```bash
# All tests
make test

# Without OCCT tests (CI-friendly)
pytest -m "not occt"

# With coverage
make test-cov
```

### Integration Tests
```bash
# With real STEP files
pytest -m "integration" -v

# Performance tests
pytest -m "slow" --benchmark-only
```

## Troubleshooting

### Common Issues

#### "No OCCT binding available"
- Install pyOCCT or pythonOCC-core (see above)
- Check Python environment and paths
- Verify system dependencies are installed

#### "Permission denied" errors
- Check file permissions on STEP files
- Ensure write access to output directories
- On macOS, check quarantine attributes

#### MCP server not responding
- Test server manually: `shapebridge-mcp`
- Check Claude Desktop MCP configuration
- Verify stdio communication works

#### Memory issues with large files
- Increase system memory limits
- Use `ulimit -v` to check virtual memory
- Consider file streaming for very large models

### Getting Help

1. **Check logs:** Enable verbose logging with `-v` flag
2. **Run diagnostics:** `shapebridge info` shows system status
3. **Test minimal case:** Use provided sample STEP files
4. **Check issues:** GitHub Issues for known problems

### Debug Mode
```bash
# Enable debug logging
export SHAPEBRIDGE_LOG_LEVEL=DEBUG

# Run with verbose output
shapebridge -v load /path/to/model.step
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SHAPEBRIDGE_LOG_LEVEL` | `INFO` | Logging level |
| `SHAPEBRIDGE_MAX_MODELS` | `10` | Session model limit |
| `SHAPEBRIDGE_CACHE_DIR` | `/tmp` | Temporary file location |
| `OCCT_PRECISION` | `0.01` | OCCT precision setting |

## Next Steps

After successful installation:

1. **Try the CLI:** `shapebridge load examples/cube.step`
2. **Test MCP integration:** Configure Claude Desktop
3. **Read the docs:** Browse [IR_SPEC.md](IR_SPEC.md) and [PHASES.md](PHASES.md)
4. **Join development:** See [CONTRIBUTING.md](../CONTRIBUTING.md)

For additional support, see the [GitHub Issues](https://github.com/eicon-vision/shapebridge/issues) or join our community discussions.