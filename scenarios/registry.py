"""
ASTRATRACK — Scenario Registry

Central registry for retrieving and browsing all standard (01–10)
and custom scenarios.
"""

from typing import Dict, List, Optional
from scenarios.definitions import ScenarioDefinition, get_standard_scenarios


class ScenarioRegistry:
    """Catalog of all registered scenarios."""

    def __init__(self):
        self._scenarios: Dict[str, ScenarioDefinition] = get_standard_scenarios()

    def get(self, scenario_id_or_name: str) -> Optional[ScenarioDefinition]:
        """Lookup scenario by ID (e.g. '01', '1', '02') or name."""
        key = str(scenario_id_or_name).strip().zfill(2)
        if key in self._scenarios:
            return self._scenarios[key]

        # Try prefix e.g. "01_baseline" -> "01"
        prefix = str(scenario_id_or_name).split("_")[0].strip().zfill(2)
        if prefix in self._scenarios:
            return self._scenarios[prefix]

        # Try matching by name
        target_name = scenario_id_or_name.upper().replace(" ", "_")
        for scen in self._scenarios.values():
            if scen.name.upper().replace(" ", "_") == target_name:
                return scen
        return None

    def list_all(self) -> List[ScenarioDefinition]:
        """Return sorted list of all available scenarios."""
        return sorted(self._scenarios.values(), key=lambda s: s.id)

    def register_custom(self, scenario: ScenarioDefinition):
        """Register a user-defined custom scenario."""
        self._scenarios[scenario.id] = scenario


# Global singleton instance
GLOBAL_REGISTRY = ScenarioRegistry()


def get_scenario(scenario_id_or_name: str) -> Optional[ScenarioDefinition]:
    """Helper to get scenario from global registry."""
    return GLOBAL_REGISTRY.get(scenario_id_or_name)


def list_scenarios() -> List[ScenarioDefinition]:
    """Helper to list all scenarios from global registry."""
    return GLOBAL_REGISTRY.list_all()

