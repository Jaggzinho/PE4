from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportResult:
    materials: int
    properties: int
    tests: int
    measurements: int
    sinottico_items: int
    component_types: int = 0
    components: int = 0
    material_component_defaults: int = 0
