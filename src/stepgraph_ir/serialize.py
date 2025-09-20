"""Deterministic serialization for STEPGraph-IR.

This module provides deterministic JSON serialization with stable ordering
for reproducible IR generation across different runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Union

import orjson

from .schema import IR, Node, Edge


def _sort_dict_recursive(obj: Any) -> Any:
    """Recursively sort dictionaries for deterministic output."""
    if isinstance(obj, dict):
        return {k: _sort_dict_recursive(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [_sort_dict_recursive(item) for item in obj]
    else:
        return obj


def _node_sort_key(node: Node) -> tuple[int, str]:
    """Generate sort key for deterministic node ordering.

    Sorts by:
    1. Node type priority (Assembly -> Part -> Geometry -> Units -> PMI)
    2. Node ID alphabetically
    """
    type_priority = {
        "Assembly": 0,
        "Part": 1,
        "Product": 2,
        "ManifoldSolidBrep": 10,
        "AdvancedFace": 11,
        "EdgeCurve": 12,
        "VertexPoint": 13,
        "Unit": 20,
        "CoordinateSystem": 21,
        "PMI_Entity": 30,
        "GeometricTolerance": 31,
        "DimensioningTolerance": 32,
        "ValidationProperty": 40,
        "MaterialProperty": 41,
        "SurfaceFinish": 42,
    }

    priority = type_priority.get(node.type, 999)
    return (priority, node.id)


def _edge_sort_key(edge: Edge) -> tuple[str, str, str]:
    """Generate sort key for deterministic edge ordering."""
    return (edge.src, edge.dst, edge.type)


def to_json_dict(ir: IR, deterministic: bool = True) -> Dict[str, Any]:
    """Convert IR to JSON-serializable dictionary.

    Args:
        ir: The IR to serialize
        deterministic: If True, sort all collections for reproducible output

    Returns:
        Dictionary representation ready for JSON serialization
    """
    nodes = ir.nodes
    edges = ir.edges

    if deterministic:
        # Sort nodes and edges for deterministic output
        nodes = sorted(nodes, key=_node_sort_key)
        edges = sorted(edges, key=_edge_sort_key)

    # Convert to dictionaries
    nodes_data = []
    for node in nodes:
        node_dict = {
            "id": node.id,
            "type": node.type,
            "attrs": _sort_dict_recursive(node.attrs) if deterministic else node.attrs,
        }
        nodes_data.append(node_dict)

    edges_data = []
    for edge in edges:
        edge_dict = {
            "src": edge.src,
            "dst": edge.dst,
            "type": edge.type,
            "attrs": _sort_dict_recursive(edge.attrs) if deterministic else edge.attrs,
        }
        edges_data.append(edge_dict)

    # Build final dictionary
    result = {
        "schema_version": ir.validation.schema_version,
        "model_id": ir.model_id,
        "validation": {
            "created_at": ir.validation.created_at,
            "node_count": ir.validation.node_count,
            "edge_count": ir.validation.edge_count,
            "is_valid": ir.validation.is_valid,
            "warnings": ir.validation.warnings,
            "errors": ir.validation.errors,
        },
        "units": _sort_dict_recursive(ir.units) if deterministic else ir.units,
        "nodes": nodes_data,
        "edges": edges_data,
        "provenance": _sort_dict_recursive(ir.provenance) if deterministic else ir.provenance,
    }

    # Add optional fields if present
    if ir.bounding_box:
        result["bounding_box"] = {
            "min_x": ir.bounding_box.min_x,
            "min_y": ir.bounding_box.min_y,
            "min_z": ir.bounding_box.min_z,
            "max_x": ir.bounding_box.max_x,
            "max_y": ir.bounding_box.max_y,
            "max_z": ir.bounding_box.max_z,
        }

    return result


def to_json_string(ir: IR, deterministic: bool = True, pretty: bool = False) -> str:
    """Convert IR to JSON string.

    Args:
        ir: The IR to serialize
        deterministic: If True, sort all collections for reproducible output
        pretty: If True, format JSON with indentation

    Returns:
        JSON string representation
    """
    data = to_json_dict(ir, deterministic=deterministic)

    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    else:
        # Use orjson for faster serialization
        return orjson.dumps(data).decode('utf-8')


def dump_jsonl(ir: IR, path: Union[str, Path], deterministic: bool = True) -> None:
    """Write IR to JSONL file (one JSON object per line).

    Args:
        path: Output file path
        ir: The IR to serialize
        deterministic: If True, sort all collections for reproducible output
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    json_data = to_json_dict(ir, deterministic=deterministic)

    with open(path, 'wb') as f:
        f.write(orjson.dumps(json_data))
        f.write(b'\n')


def load_jsonl(path: Union[str, Path]) -> Iterator[IR]:
    """Load IR objects from JSONL file.

    Args:
        path: Input file path

    Yields:
        IR objects loaded from the file

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If JSON parsing fails or schema is invalid
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {path}")

    with open(path, 'rb') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = orjson.loads(line)
                ir = _dict_to_ir(data)
                yield ir
            except (orjson.JSONDecodeError, ValueError) as e:
                raise ValueError(f"Failed to parse line {line_num}: {e}") from e


def _dict_to_ir(data: Dict[str, Any]) -> IR:
    """Convert dictionary back to IR object."""
    from .schema import IR, Node, Edge, BoundingBox, ValidationInfo

    # Reconstruct validation info
    val_data = data.get("validation", {})
    validation = ValidationInfo(
        schema_version=val_data.get("schema_version", "0.1.0"),
        created_at=val_data.get("created_at", ""),
        node_count=val_data.get("node_count", 0),
        edge_count=val_data.get("edge_count", 0),
        warnings=val_data.get("warnings", []),
        errors=val_data.get("errors", []),
    )

    # Reconstruct nodes
    nodes = []
    for node_data in data.get("nodes", []):
        node = Node(
            id=node_data["id"],
            type=node_data["type"],
            attrs=node_data.get("attrs", {})
        )
        nodes.append(node)

    # Reconstruct edges
    edges = []
    for edge_data in data.get("edges", []):
        edge = Edge(
            src=edge_data["src"],
            dst=edge_data["dst"],
            type=edge_data["type"],
            attrs=edge_data.get("attrs", {})
        )
        edges.append(edge)

    # Reconstruct bounding box if present
    bbox = None
    if "bounding_box" in data:
        bbox_data = data["bounding_box"]
        bbox = BoundingBox(
            min_x=bbox_data["min_x"],
            min_y=bbox_data["min_y"],
            min_z=bbox_data["min_z"],
            max_x=bbox_data["max_x"],
            max_y=bbox_data["max_y"],
            max_z=bbox_data["max_z"],
        )

    # Create IR object
    ir = IR(
        model_id=data["model_id"],
        nodes=nodes,
        edges=edges,
        units=data.get("units", {"length": "mm", "angle": "deg"}),
        provenance=data.get("provenance", {}),
        validation=validation,
        bounding_box=bbox,
    )

    return ir


def batch_dump_jsonl(irs: List[IR], path: Union[str, Path], deterministic: bool = True) -> None:
    """Write multiple IR objects to a JSONL file.

    Args:
        irs: List of IR objects to serialize
        path: Output file path
        deterministic: If True, sort all collections for reproducible output
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, 'wb') as f:
        for ir in irs:
            json_data = to_json_dict(ir, deterministic=deterministic)
            f.write(orjson.dumps(json_data))
            f.write(b'\n')