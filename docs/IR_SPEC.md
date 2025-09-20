# STEPGraph-IR Specification v0.1.0

This document defines the STEPGraph Intermediate Representation (IR), a deterministic graph-based format for representing CAD geometry and associated metadata.

## Overview

STEPGraph-IR provides a stable, versioned representation of CAD models that:
- Enables deterministic analysis across different OCCT versions
- Supports incremental processing and caching
- Facilitates machine learning on geometric data
- Maintains full traceability from source STEP files

## Core Concepts

### Graph Structure
The IR represents CAD data as a directed graph where:
- **Nodes** represent geometric entities, metadata, or semantic information
- **Edges** represent relationships between entities
- **Attributes** store properties and computed values

### Deterministic Ordering
All collections (nodes, edges) are sorted using stable criteria:
1. **Node Priority:** Assembly → Part → Geometry → Units → PMI → Properties
2. **Alphabetical ID:** Within same type, sorted by node ID
3. **Edge Sorting:** By (source, destination, edge_type) tuple

## Schema Definition

### Node Types

#### Hierarchical Containers
```python
NodeType = Literal[
    "Assembly",      # Top-level assembly
    "Part",          # Individual part/component
    "Product",       # Product definition
]
```

#### Geometric Entities (B-rep Topology)
```python
NodeType = Literal[
    "ManifoldSolidBrep",  # Solid body
    "AdvancedFace",       # Face with surface
    "EdgeCurve",          # Edge with curve
    "VertexPoint",        # Vertex with point
]
```

#### Metadata & Units
```python
NodeType = Literal[
    "Unit",               # Unit definition
    "CoordinateSystem",   # Coordinate frame
]
```

#### Product Manufacturing Information (PMI)
```python
NodeType = Literal[
    "PMI_Entity",             # Generic PMI entity
    "GeometricTolerance",     # GD&T tolerance
    "DimensioningTolerance",  # Dimensional tolerance
]
```

#### Properties & Validation
```python
NodeType = Literal[
    "ValidationProperty",  # Analysis results
    "MaterialProperty",    # Material data
    "SurfaceFinish",      # Surface texture
]
```

### Edge Types

#### Hierarchical Relationships
```python
EdgeType = Literal[
    "contains",     # Assembly contains Part
    "part_of",      # Part belongs to Assembly
    "instance_of",  # Instance of definition
]
```

#### Topological Relationships
```python
EdgeType = Literal[
    "bounded_by",   # Face bounded by Edge
    "adjacent_to",  # Edge adjacent to Edge
    "shares_edge",  # Faces share Edge
    "shares_vertex", # Edges share Vertex
]
```

#### Semantic Relationships
```python
EdgeType = Literal[
    "has_pmi",      # Entity has PMI annotation
    "has_material", # Part has Material
    "has_tolerance", # Entity has Tolerance
    "references",   # Generic reference
]
```

#### Units & Coordinates
```python
EdgeType = Literal[
    "measured_in",      # Value measured in Unit
    "coordinate_system", # Uses CoordinateSystem
]
```

## IR Structure

### Root Container
```python
@dataclass
class IR:
    model_id: str                    # Unique model identifier
    nodes: List[Node]                # All nodes in sorted order
    edges: List[Edge]                # All edges in sorted order
    units: Dict[str, str]            # Unit mapping
    provenance: Dict[str, Any]       # Source metadata
    validation: ValidationInfo       # Validation results
    bounding_box: Optional[BoundingBox] # Overall bounding box
```

### Node Definition
```python
@dataclass
class Node:
    id: str                      # Unique node identifier
    type: NodeType               # Node type from enum
    attrs: Dict[str, Any]        # Node attributes
```

### Edge Definition
```python
@dataclass
class Edge:
    src: str                     # Source node ID
    dst: str                     # Destination node ID
    type: EdgeType               # Edge type from enum
    attrs: Dict[str, Any]        # Edge attributes
```

### Validation Information
```python
@dataclass
class ValidationInfo:
    schema_version: str = "0.1.0"    # IR schema version
    created_at: str                  # ISO timestamp
    node_count: int = 0              # Total nodes
    edge_count: int = 0              # Total edges
    warnings: List[str] = []         # Validation warnings
    errors: List[str] = []           # Validation errors
    is_valid: bool                   # Overall validity
```

## Serialization Format

### JSONL Structure
Each IR is serialized as a single JSON object per line:

```json
{
  "schema_version": "0.1.0",
  "model_id": "example_part",
  "validation": {
    "created_at": "2024-01-01T12:00:00.000Z",
    "node_count": 3,
    "edge_count": 2,
    "is_valid": true,
    "warnings": [],
    "errors": []
  },
  "units": {
    "length": "mm",
    "angle": "deg"
  },
  "nodes": [
    {
      "id": "part_root",
      "type": "Part",
      "attrs": {
        "name": "Example Part",
        "topology": {"faces": 6, "edges": 12, "vertices": 8}
      }
    }
  ],
  "edges": [],
  "provenance": {
    "phase": "0",
    "generator": "ShapeBridge",
    "source_file": "/path/to/model.step"
  }
}
```

### Deterministic Serialization
- All dictionaries sorted by key
- Arrays sorted by stable criteria
- Floating-point precision standardized
- Timestamps in ISO 8601 UTC format

## Node Attribute Schemas

### Part Node Attributes
```python
{
  "name": str,                    # Part name
  "description": Optional[str],   # Part description
  "topology": {                  # Topological counts
    "solids": int,
    "shells": int,
    "faces": int,
    "edges": int,
    "vertices": int
  },
  "bounding_box": {              # Axis-aligned bounding box
    "min_x": float, "min_y": float, "min_z": float,
    "max_x": float, "max_y": float, "max_z": float
  },
  "surface_area": Optional[float], # Total surface area
  "volume": Optional[float],       # Solid volume
  "mass": Optional[float],         # Mass (if density known)
  "center_of_mass": Optional[List[float]], # [x, y, z]
  "material": Optional[str],       # Material name/ID
}
```

### Face Node Attributes
```python
{
  "surface_type": str,           # "plane", "cylinder", "sphere", etc.
  "area": Optional[float],       # Face area
  "normal": Optional[List[float]], # Surface normal [x, y, z]
  "curvature": Optional[Dict],   # Curvature information
  "texture": Optional[str],      # Surface texture/finish
}
```

### Edge Node Attributes
```python
{
  "curve_type": str,             # "line", "circle", "spline", etc.
  "length": Optional[float],     # Edge length
  "start_point": Optional[List[float]], # [x, y, z]
  "end_point": Optional[List[float]],   # [x, y, z]
  "tangent": Optional[List[float]],     # Tangent vector
}
```

## Unit Normalization

### Standard Units
All numeric values are normalized to consistent units:
- **Length:** millimeters (mm)
- **Angle:** degrees (deg)
- **Area:** square millimeters (mm²)
- **Volume:** cubic millimeters (mm³)
- **Mass:** kilograms (kg)

### Unit Conversion
Original units are preserved in provenance:
```python
{
  "provenance": {
    "original_units": {"length": "inches", "angle": "radians"},
    "conversion_factors": {"length": 25.4, "angle": 57.2958}
  }
}
```

## Validation Rules

### Structural Validation
1. All node IDs must be unique
2. All edge references must point to existing nodes
3. No self-loops allowed in edges
4. Graph must be weakly connected

### Semantic Validation
1. Assembly nodes should contain Part nodes
2. Part nodes should contain geometry nodes
3. Units must be consistent within scope
4. Bounding boxes should be properly nested

### Schema Evolution
- **Minor versions** (0.1.x): Additive changes only
- **Major versions** (1.x.x): May include breaking changes
- Migration tools provided for major version upgrades

## Phase 0 Limitations

Current implementation includes:
- ✅ Basic topology counting
- ✅ Bounding box calculation
- ✅ Unit detection and normalization
- ✅ Deterministic serialization

Planned for Phase 1:
- 🚧 Complete B-rep topology graph
- 🚧 Surface and curve geometry
- 🚧 PMI extraction
- 🚧 Advanced geometric properties

## Example Usage

### Loading IR
```python
from stepgraph_ir.serialize import load_jsonl

for ir in load_jsonl("model.jsonl"):
    print(f"Model: {ir.model_id}")
    print(f"Nodes: {len(ir.nodes)}")
    print(f"Valid: {ir.validation.is_valid}")
```

### Querying Graph
```python
# Find all Part nodes
parts = ir.get_nodes_by_type("Part")

# Get assembly structure
for assembly in ir.get_nodes_by_type("Assembly"):
    contained_parts = ir.get_edges_from_node(assembly.id)
    print(f"{assembly.attrs['name']} contains {len(contained_parts)} parts")
```

### Geometric Analysis
```python
part = ir.get_node_by_id("main_part")
topology = part.attrs["topology"]
print(f"Part has {topology['faces']} faces, {topology['edges']} edges")

if "bounding_box" in part.attrs:
    bbox = part.attrs["bounding_box"]
    size_x = bbox["max_x"] - bbox["min_x"]
    print(f"Part width: {size_x} mm")
```

## Compatibility

### STEP Standards
- ✅ AP203 (Configuration controlled 3D design)
- ✅ AP214 (Core data for automotive mechanical design)
- 🚧 AP242 (Managed model based 3d engineering)

### CAD Systems
Tested with STEP files from:
- SolidWorks
- Fusion 360
- FreeCAD
- OpenCASCADE sample files

## Future Extensions

### Phase 1 Additions
- Complete geometric representation
- Manufacturing features
- Assembly constraints
- Material properties

### Phase 2 Additions
- Parametric relationships
- Design history
- Simulation results
- Optimization data

This specification will evolve with each phase while maintaining backward compatibility through semantic versioning.