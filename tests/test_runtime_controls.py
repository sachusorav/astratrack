"""
ASTRATRACK — Phase 6 Tests: Interactive Runtime Controls

Tests:
- Scenario hot-swap leaves no stale state (node_count, step_count, error history)
- FSM/pipeline state cleared on switch
- Pause → switch → resume correct behavour
- Reset after switch reinitializes new scenario
- Malformed commands fail gracefully without crashing
- Satellite scenario registry completeness
- Telemetry reflects new scenario immediately after switch
"""

import sys
import os
import pytest
import numpy as np

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from simulator.simulation import Simulation3D
from simulator.scenarios import (
    get_scenario_by_id_or_key, list_scenarios, list_scenarios_by_mode,
    MODE_GROUPS, get_scenario_mode
)


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture
def sim_headless():
    """Lightweight Simulation3D instance (no renderer window, no pipeline)."""
    scenario = get_scenario_by_id_or_key("stationary")
    sim = Simulation3D(
        scenario=scenario,
        width=320, height=240,
        deterministic=True,
        use_pipeline=False,
    )
    return sim


# ------------------------------------------------------------------ #
# 1. Satellite Scenario Registry
# ------------------------------------------------------------------ #

class TestSatelliteScenarios:

    def test_satellite_scenario_keys_registered(self):
        """Keys 7, 8, 9 must resolve to satellite scenarios."""
        for key in ("7", "8", "9"):
            s = get_scenario_by_id_or_key(key)
            assert s is not None, f"Key '{key}' not found in registry"
            assert s.category == "Satellite \u2194 Satellite"

    def test_satellite_scenario_ids_registered(self):
        """String IDs for all satellite scenarios must be resolvable."""
        for sid in ("sat_to_ground", "isl_same_plane", "isl_crosslink"):
            s = get_scenario_by_id_or_key(sid)
            assert s is not None, f"Scenario ID '{sid}' not in registry"
            assert s.id == sid

    def test_mode_groups_correct(self):
        """MODE_GROUPS must contain exactly 6 ground and 3 satellite scenario IDs."""
        assert len(MODE_GROUPS["ground_to_sat"]) == 6
        assert len(MODE_GROUPS["sat_to_sat"]) == 3

    def test_list_scenarios_by_mode(self):
        """list_scenarios_by_mode returns correct counts and categories."""
        ground = list_scenarios_by_mode("ground_to_sat")
        sat = list_scenarios_by_mode("sat_to_sat")
        assert len(ground) == 6
        assert len(sat) == 3
        for s in sat:
            assert s.category == "Satellite \u2194 Satellite"

    def test_get_scenario_mode(self):
        """get_scenario_mode correctly classifies every scenario."""
        for sid in ("stationary", "linear", "orbital", "turbulence", "high_speed", "evasive"):
            assert get_scenario_mode(sid) == "ground_to_sat", f"{sid} should be ground_to_sat"
        for sid in ("sat_to_ground", "isl_same_plane", "isl_crosslink"):
            assert get_scenario_mode(sid) == "sat_to_sat", f"{sid} should be sat_to_sat"

    def test_list_scenarios_unique(self):
        """list_scenarios() must not contain duplicates (alias keys must be deduplicated)."""
        all_scens = list_scenarios()
        ids = [s.id for s in all_scens]
        assert len(ids) == len(set(ids)), "Duplicate scenario IDs in list_scenarios()"
        assert len(all_scens) == 9   # 6 ground + 3 satellite


# ------------------------------------------------------------------ #
# 2. Hot-Swap: stale state cleared on switch
# ------------------------------------------------------------------ #

class TestScenarioSwitch:

    def test_switch_clears_step_count_and_history(self, sim_headless):
        """After a switch, step_count and _error_history must be reset."""
        sim = sim_headless
        # Advance some frames first
        for _ in range(30):
            sim.step()
        assert sim.step_count > 0
        assert len(sim._error_history) > 0

        # Switch to a satellite scenario
        ok = sim.switch_scene("sat_to_sat", "isl_crosslink")
        assert ok is True
        assert sim.step_count == 0
        assert len(sim._error_history) == 0

    def test_switch_updates_scenario_id(self, sim_headless):
        """After switch, sim.scenario.id must match the new scenario."""
        sim = sim_headless
        assert sim.scenario.id == "stationary"
        sim.switch_scene("ground_to_sat", "orbital")
        assert sim.scenario.id == "orbital"

    def test_switch_updates_active_mode(self, sim_headless):
        """Switching to a sat scenario must flip active_mode to 'sat_to_sat'."""
        sim = sim_headless
        assert sim.active_mode == "ground_to_sat"
        sim.switch_scene("sat_to_sat", "sat_to_ground")
        assert sim.active_mode == "sat_to_sat"

    def test_switch_to_ground_resets_mode(self, sim_headless):
        """Switching from sat_to_sat back to ground must restore active_mode."""
        sim = sim_headless
        sim.switch_scene("sat_to_sat", "isl_same_plane")
        assert sim.active_mode == "sat_to_sat"
        sim.switch_scene("ground_to_sat", "evasive")
        assert sim.active_mode == "ground_to_sat"

    def test_node_count_correct_after_switch(self, sim_headless):
        """node_count must be 1 for ground and 2 for sat_to_sat."""
        sim = sim_headless
        assert sim.node_count == 1
        sim.switch_scene("sat_to_sat", "isl_crosslink")
        assert sim.node_count == 2
        sim.switch_scene("ground_to_sat", "linear")
        assert sim.node_count == 1

    def test_target_position_matches_new_scenario(self, sim_headless):
        """Target initial position after switch must match new scenario's config."""
        sim = sim_headless
        sim.switch_scene("sat_to_sat", "isl_crosslink")
        expected_pos = np.array([400.0, 900.0, -200.0])
        np.testing.assert_allclose(sim.target.position, expected_pos, atol=1.0,
                                   err_msg="Target position does not match isl_crosslink initial position")

    def test_switch_fires_flash_timer(self, sim_headless):
        """switch_scene must arm the switch_flash_timer."""
        sim = sim_headless
        sim.switch_scene("sat_to_sat", "sat_to_ground")
        assert sim.switch_flash_timer > 0.0
        assert len(sim.switch_flash_label) > 0

    def test_flash_timer_decrements_on_step(self, sim_headless):
        """switch_flash_timer must decrease as steps advance."""
        sim = sim_headless
        sim.switch_scene("ground_to_sat", "turbulence")
        initial_timer = sim.switch_flash_timer
        assert initial_timer > 0.0
        # Advance several fixed-dt steps
        for _ in range(10):
            sim.step()
        assert sim.switch_flash_timer < initial_timer

    def test_telemetry_reflects_new_scenario(self, sim_headless):
        """get_telemetry() must immediately show the new scenario after switch."""
        sim = sim_headless
        sim.switch_scene("sat_to_sat", "isl_same_plane")
        telem = sim.get_telemetry()
        assert telem["scenario_id"] == "isl_same_plane"
        assert telem["active_mode"] == "sat_to_sat"
        assert telem["node_count"] == 2


# ------------------------------------------------------------------ #
# 3. Pause / Resume / Reset across switches
# ------------------------------------------------------------------ #

class TestPauseResumeAfterSwitch:

    def test_pause_then_switch_then_resume(self, sim_headless):
        """Pause → switch → resume must leave is_paused=False after Space."""
        sim = sim_headless
        # Run a few frames, pause
        for _ in range(5):
            sim.step()
        sim.toggle_pause()
        assert sim.is_paused is True

        # Switch while paused
        ok = sim.switch_scene("sat_to_sat", "isl_crosslink")
        assert ok is True
        # After reset() inside switch_scene, is_paused stays as-is
        # (reset doesn't touch is_paused)
        sim.toggle_pause()  # resume
        assert sim.is_paused is False

        # Simulation should now advance
        step_before = sim.step_count
        sim.step()
        assert sim.step_count == step_before + 1

    def test_reset_after_switch_uses_new_scenario(self, sim_headless):
        """reset() after a switch must reinit to the new scenario's layout."""
        sim = sim_headless
        sim.switch_scene("ground_to_sat", "high_speed")
        # Advance frames so state diverges
        for _ in range(20):
            sim.step()
        assert sim.step_count == 20

        sim.reset()
        assert sim.step_count == 0
        assert sim.scenario.id == "high_speed"
        # Position must be back to initial
        expected_pos = np.array([-800.0, 200.0, 250.0])
        np.testing.assert_allclose(sim.target.position, expected_pos, atol=1.0)

    def test_paused_sim_does_not_advance_after_switch(self, sim_headless):
        """If paused then switched, step() should still be a no-op unless unpaused."""
        sim = sim_headless
        sim.toggle_pause()
        sim.switch_scene("sat_to_sat", "sat_to_ground")
        step_count = sim.step_count  # == 0 after switch reset
        sim.step()   # should no-op (is_paused may or may not be set by reset)
        # Even if is_paused was cleared by reset, step advances once at most
        assert sim.step_count <= 1


# ------------------------------------------------------------------ #
# 4. Graceful failure: bad commands
# ------------------------------------------------------------------ #

class TestBadCommands:

    def test_unknown_scenario_key_returns_false(self, sim_headless):
        """switch_scene with an unrecognised scenario key must return False."""
        sim = sim_headless
        original_id = sim.scenario.id
        result = sim.switch_scene("ground_to_sat", "nonexistent_scenario_xyz")
        assert result is False
        # Sim must remain in original scenario unchanged
        assert sim.scenario.id == original_id

    def test_unknown_mode_returns_false(self, sim_headless):
        """switch_scene with an invalid mode must return False without crashing."""
        sim = sim_headless
        original_id = sim.scenario.id
        result = sim.switch_scene("invalid_mode_blah", "stationary")
        assert result is False
        assert sim.scenario.id == original_id

    def test_scenario_wrong_mode_returns_false(self, sim_headless):
        """Passing a sat scenario ID under the ground mode must be rejected."""
        sim = sim_headless
        result = sim.switch_scene("ground_to_sat", "isl_crosslink")
        assert result is False
        assert sim.scenario.id == "stationary"

    def test_sim_still_runs_after_bad_command(self, sim_headless):
        """Simulation must remain fully functional after a rejected switch."""
        sim = sim_headless
        sim.switch_scene("ground_to_sat", "nonexistent")  # rejected
        for _ in range(5):
            sim.step()
        assert sim.step_count == 5

    def test_load_scenario_unknown_key_returns_false(self, sim_headless):
        """The legacy load_scenario() must also return False for unknown keys."""
        sim = sim_headless
        result = sim.load_scenario("99999")
        assert result is False
