"""
ASTRATRACK — Target-Loss Detection and Re-Acquisition FSM

Implements 7 system states:
- SEARCHING
- ACQUIRING
- LOCKED
- TRACKING
- TARGET_LOST
- PREDICTING
- REACQUIRING

Coordinates local Archimedean spiral and expanded search patterns,
tracks recovery performance metrics, and provides setpoints for the camera controller.
"""

import math
from enum import Enum
from dataclasses import dataclass, field
from typing import Tuple, List, Optional, Any


class FSMState(Enum):
    """System tracking states."""
    SEARCHING = "SEARCHING"
    ACQUIRING = "ACQUIRING"
    LOCKED = "LOCKED"
    TRACKING = "TRACKING"
    TARGET_LOST = "TARGET_LOST"
    PREDICTING = "PREDICTING"
    REACQUIRING = "REACQUIRING"


@dataclass
class ReacquisitionMetrics:
    """Metrics tracking recovery performance."""
    number_of_losses: int = 0
    number_of_recoveries: int = 0
    failed_recoveries: int = 0
    last_recovery_time: float = 0.0
    recovery_times: List[float] = field(default_factory=list)

    @property
    def mean_recovery_time(self) -> float:
        if not self.recovery_times:
            return 0.0
        return float(sum(self.recovery_times) / len(self.recovery_times))

    @property
    def recovery_rate_pct(self) -> float:
        total = self.number_of_recoveries + self.failed_recoveries
        if total == 0:
            return 100.0
        return float((self.number_of_recoveries / total) * 100.0)


class SearchPatternGenerator:
    """
    Generates search trajectory offsets for target re-acquisition.
    Phase 1: Expanding Archimedean spiral around predicted position.
    Phase 2: Expanded wide-area raster/box search.
    """

    def __init__(self,
                 local_max_radius: float = 120.0,
                 expansion_rate: float = 40.0,
                 spiral_angular_speed: float = 12.0):
        self.local_max_radius = local_max_radius
        self.expansion_rate = expansion_rate
        self.spiral_angular_speed = spiral_angular_speed

    def get_offset(self, t_search: float, is_expanded: bool = False) -> Tuple[float, float]:
        """
        Compute (dx, dy) search offset relative to predicted position.
        """
        if not is_expanded:
            # Local expanding Archimedean spiral
            theta = self.spiral_angular_speed * t_search
            r = min(self.local_max_radius, self.expansion_rate * t_search)
            dx = r * math.cos(theta)
            dy = r * math.sin(theta)
            return (dx, dy)
        else:
            # Expanded outward box/raster search
            theta = (self.spiral_angular_speed * 0.6) * t_search
            r = self.local_max_radius + (self.expansion_rate * 1.5) * t_search
            r = min(350.0, r)
            dx = r * math.cos(theta)
            dy = r * math.sin(theta)
            return (dx, dy)


class TrackingFSM:
    """
    Finite State Machine orchestrating target acquisition, tracking,
    dropout management, and re-acquisition.
    """

    def __init__(self,
                 confidence_threshold: float = 0.50,
                 confirm_frames: int = 2,
                 lock_error_threshold_px: float = 35.0,
                 predict_coast_duration: float = 0.8,
                 local_search_duration: float = 3.0,
                 expanded_search_duration: float = 5.0):
        """
        Args:
            confidence_threshold: Minimum detector confidence to declare target seen.
            confirm_frames: Number of consecutive frames needed to confirm ACQUIRE -> LOCKED.
            lock_error_threshold_px: Max tracking error to transition LOCKED -> TRACKING.
            predict_coast_duration: Duration (seconds) to coast in PREDICTING before searching.
            local_search_duration: Duration (seconds) of local spiral search before expanding.
            expanded_search_duration: Duration (seconds) of expanded search before declaring fail.
        """
        self.confidence_threshold = confidence_threshold
        self.confirm_frames = confirm_frames
        self.lock_error_threshold_px = lock_error_threshold_px
        self.predict_coast_duration = predict_coast_duration
        self.local_search_duration = local_search_duration
        self.expanded_search_duration = expanded_search_duration

        # State
        self.state = FSMState.SEARCHING
        self.metrics = ReacquisitionMetrics()
        self.search_generator = SearchPatternGenerator()

        # Timers & Counters
        self._state_time = 0.0
        self._confirm_counter = 0
        self._loss_start_time = 0.0
        self._search_start_time = 0.0
        self._is_search_expanded = False

        # Target & Prediction coordinates
        self.last_known_pos: Optional[Tuple[float, float]] = None
        self.predicted_pos: Optional[Tuple[float, float]] = None
        self.current_search_offset: Tuple[float, float] = (0.0, 0.0)

    def update(self,
               detection_pos: Optional[Tuple[float, float]],
               confidence: float,
               estimated_pos: Tuple[float, float],
               predicted_pos: Tuple[float, float],
               camera_center: Tuple[float, float],
               sim_time: float,
               dt: float = 0.02) -> FSMState:
        """
        Advance the FSM state machine by one time-step.

        Args:
            detection_pos: (x, y) if target detected this frame, else None.
            confidence: Detector confidence score [0, 1].
            estimated_pos: Current Kalman estimated position.
            predicted_pos: Forward extrapolated predicted position.
            camera_center: Camera FOV center boresight.
            sim_time: Current simulation timestamp.
            dt: Time step duration.

        Returns:
            Current active FSMState.
        """
        self._state_time += dt
        has_detection = (detection_pos is not None) and (confidence >= self.confidence_threshold)

        if has_detection:
            self.last_known_pos = detection_pos
        self.predicted_pos = predicted_pos

        # ============================================================== #
        # State Transitions
        # ============================================================== #

        if self.state == FSMState.SEARCHING:
            self.current_search_offset = (0.0, 0.0)
            if has_detection:
                self._transition_to(FSMState.ACQUIRING)
                self._confirm_counter = 1

        elif self.state == FSMState.ACQUIRING:
            if has_detection:
                self._confirm_counter += 1
                if self._confirm_counter >= self.confirm_frames:
                    self._transition_to(FSMState.LOCKED)
            else:
                self._confirm_counter = 0
                self._transition_to(FSMState.SEARCHING)

        elif self.state == FSMState.LOCKED:
            # Check boresight alignment error
            err_px = math.hypot(estimated_pos[0] - camera_center[0],
                                estimated_pos[1] - camera_center[1])
            if has_detection:
                if err_px <= self.lock_error_threshold_px:
                    self._transition_to(FSMState.TRACKING)
            else:
                self._handle_target_loss(sim_time)

        elif self.state == FSMState.TRACKING:
            if not has_detection:
                self._handle_target_loss(sim_time)

        elif self.state == FSMState.TARGET_LOST:
            # Immediately transition to PREDICTING
            self._transition_to(FSMState.PREDICTING)

        elif self.state == FSMState.PREDICTING:
            if has_detection:
                self._handle_reacquisition_success(sim_time)
            elif self._state_time >= self.predict_coast_duration:
                # Coast limit reached, initiate active local search
                self._transition_to(FSMState.REACQUIRING)
                self._search_start_time = sim_time
                self._is_search_expanded = False

        elif self.state == FSMState.REACQUIRING:
            if has_detection:
                self._handle_reacquisition_success(sim_time)
            else:
                t_search = sim_time - self._search_start_time
                if not self._is_search_expanded:
                    if t_search >= self.local_search_duration:
                        # Local search timed out: expand search region!
                        self._is_search_expanded = True
                    else:
                        self.current_search_offset = self.search_generator.get_offset(
                            t_search, is_expanded=False
                        )
                else:
                    if t_search >= (self.local_search_duration + self.expanded_search_duration):
                        # Expanded search failed: declare failed recovery and revert to SEARCHING
                        self.metrics.failed_recoveries += 1
                        self.current_search_offset = (0.0, 0.0)
                        self._transition_to(FSMState.SEARCHING)
                    else:
                        self.current_search_offset = self.search_generator.get_offset(
                            t_search - self.local_search_duration, is_expanded=True
                        )

        return self.state

    def _transition_to(self, new_state: FSMState):
        self.state = new_state
        self._state_time = 0.0

    def _handle_target_loss(self, sim_time: float):
        self.metrics.number_of_losses += 1
        self._loss_start_time = sim_time
        self._transition_to(FSMState.TARGET_LOST)

    def _handle_reacquisition_success(self, sim_time: float):
        rec_time = max(0.01, sim_time - self._loss_start_time)
        self.metrics.number_of_recoveries += 1
        self.metrics.last_recovery_time = rec_time
        self.metrics.recovery_times.append(rec_time)
        self.current_search_offset = (0.0, 0.0)
        self._transition_to(FSMState.LOCKED)

    def get_tracking_setpoint(self, camera_center: Tuple[float, float]) -> Tuple[float, float]:
        """
        Compute desired target setpoint for the camera controller based on current state.
        """
        if self.state in (FSMState.LOCKED, FSMState.TRACKING, FSMState.ACQUIRING):
            return self.last_known_pos or camera_center
        elif self.state == FSMState.PREDICTING:
            return self.predicted_pos or self.last_known_pos or camera_center
        elif self.state == FSMState.REACQUIRING:
            base = self.predicted_pos or self.last_known_pos or camera_center
            return (base[0] + self.current_search_offset[0],
                    base[1] + self.current_search_offset[1])
        else:  # SEARCHING
            return camera_center

    def reset(self):
        """Reset state machine and metrics."""
        self.state = FSMState.SEARCHING
        self._state_time = 0.0
        self._confirm_counter = 0
        self._loss_start_time = 0.0
        self._search_start_time = 0.0
        self._is_search_expanded = False
        self.last_known_pos = None
        self.predicted_pos = None
        self.current_search_offset = (0.0, 0.0)
        self.metrics = ReacquisitionMetrics()
