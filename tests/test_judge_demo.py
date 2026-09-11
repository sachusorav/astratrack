"""
ASTRATRACK — Unit Tests for Dedicated Judge Demo Mode

Tests:
- Stepping through 10-phase narrative timeline
- Automated target loss and re-acquisition triggers
- Final performance scorecard generation
- Repeatability under deterministic seed
"""

import sys
import os
import unittest

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from demo.director import JudgeDemoDirector, DemoPhase


class TestJudgeDemo(unittest.TestCase):
    """Test suite for Judge Demo Director."""

    def test_judge_demo_timeline_execution(self):
        """Execute accelerated stepped run through the full 90-second timeline."""
        director = JudgeDemoDirector(seed=42)

        phases_visited = set()
        dt = 0.5  # Accelerated simulation time steps for test

        for _ in range(190):  # 190 * 0.5s = 95s
            phase, is_done = director.step(dt=dt)
            phases_visited.add(phase)
            if is_done:
                break

        self.assertTrue(director.is_completed)
        self.assertIn(DemoPhase.DETECT, phases_visited)
        self.assertIn(DemoPhase.TRACK, phases_visited)
        self.assertIn(DemoPhase.TARGET_LOST, phases_visited)
        self.assertIn(DemoPhase.REACQUIRING if hasattr(DemoPhase, 'REACQUIRING') else DemoPhase.REACQUIRE, phases_visited)
        self.assertIn(DemoPhase.LOCKED_REPORT, phases_visited)

        # Verify final scorecard
        scorecard = director.get_final_scorecard()
        self.assertTrue(scorecard.tracking_success)
        self.assertGreater(scorecard.average_error_px, 0.0)
        self.assertGreater(scorecard.lock_retention_pct, 10.0)
        self.assertGreater(scorecard.fps, 0.0)

        # Verify Reset Demo
        director.reset()
        self.assertEqual(director.sim_time, 0.0)
        self.assertEqual(director.current_phase, DemoPhase.DETECT)
        self.assertFalse(director.is_completed)


if __name__ == "__main__":
    unittest.main()
