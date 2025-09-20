"""STEPGraph Intermediate Representation (IR) package.

This package provides the schema, serialization, and utilities for
deterministic STEP file analysis and representation.
"""

from .schema import IR, Node, Edge, NodeType
from .serialize import to_json_dict, dump_jsonl, load_jsonl

__version__ = "0.1.0"
__all__ = ["IR", "Node", "Edge", "NodeType", "to_json_dict", "dump_jsonl", "load_jsonl"]