"""ShapeBridge MCP Server package.

Provides MCP (Model Context Protocol) server implementation for Claude Code
integration with deterministic STEP file processing and IR generation.
"""

from .server import main as server_main
from .tools import ShapeBridgeSession

__version__ = "0.1.0"
__all__ = ["server_main", "ShapeBridgeSession"]