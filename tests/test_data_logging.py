"""
ASTRATRACK — QA Automated Tests: Data Logging & Session Management

Validates:
- SessionManager directory and metadata creation
- PerformanceLogger lifecycle (start, record, flush, stop)
- CSV header integrity and column parsing
- Valid CSV row serialization across multiple frames
- Robustness against inactive logging state
"""

import os
import csv
import json
import pytest
from logging_.session import SessionManager
from logging_.logger import PerformanceLogger


class TestDataLogging:
    """Automated test suite for data logging and session storage."""

    @pytest.fixture
    def temp_session_dir(self, tmp_path):
        return str(tmp_path / "test_sessions")

    def test_session_manager_creates_dir_and_metadata(self, temp_session_dir):
        sm = SessionManager(base_dir=temp_session_dir)
        config_snapshot = {"camera_fov": 10.0, "detector": "classical", "seed": 42}
        
        session_path = sm.start_session(config_dict=config_snapshot)
        
        assert os.path.exists(session_path), "Session directory was not created"
        meta_file = os.path.join(session_path, "metadata.json")
        assert os.path.exists(meta_file), "Session metadata.json was not created"
        
        with open(meta_file, "r") as f:
            metadata = json.load(f)
            assert metadata["session_id"] == sm.session_id
            assert metadata["config"]["camera_fov"] == 10.0
            assert "start_time" in metadata

    def test_performance_logger_header_and_lifecycle(self, temp_session_dir):
        sm = SessionManager(base_dir=temp_session_dir)
        logger = PerformanceLogger(session_manager=sm)
        
        assert not logger.is_active, "Logger should be inactive before start()"
        
        # Calling record before start should be a graceful no-op
        logger.record(
            gt_pos=(100, 100), det_pos=(100, 100), est_pos=(100, 100),
            pred_pos=(100, 100), err_track_px=0.0, err_gt_px=0.0,
            err_deg=0.0, fps=60.0, is_locked=True, coast_frames=0,
            pid_pan=0.0, pid_tilt=0.0, turb_level=0.0, vib_level=0.0, noise_level=0.0
        )
        assert logger._frame_count == 0

        # Start logging session
        logger.start(config_dict={"test": "qa"})
        assert logger.is_active, "Logger should be active after start()"
        log_file = sm.log_path
        assert os.path.exists(log_file), "Log CSV file was not created"

        # Verify header
        logger.stop()
        assert not logger.is_active, "Logger should be inactive after stop()"
        
        with open(log_file, "r", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == PerformanceLogger.HEADER
            assert "timestamp" in header
            assert "err_track_px" in header
            assert "lock_status" in header

    def test_performance_logger_record_and_data_integrity(self, temp_session_dir):
        sm = SessionManager(base_dir=temp_session_dir)
        logger = PerformanceLogger(session_manager=sm)
        logger.start()

        # Write 10 test frames with varying values
        for i in range(10):
            logger.record(
                gt_pos=(320.0 + i, 240.0 - i),
                det_pos=(320.5 + i, 239.5 - i),
                est_pos=(320.2 + i, 239.8 - i),
                pred_pos=(321.0 + i, 239.0 - i),
                err_track_px=1.5 * i,
                err_gt_px=1.2 * i,
                err_deg=0.02 * i,
                fps=59.5,
                is_locked=(i % 2 == 0),
                coast_frames=i if (i % 2 != 0) else 0,
                pid_pan=0.1 * i,
                pid_tilt=-0.05 * i,
                turb_level=0.1 * i,
                vib_level=0.05 * i,
                noise_level=0.2 * i
            )

        assert logger._frame_count == 10
        logger.stop()

        # Read back and parse all rows
        with open(sm.log_path, "r", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)
            assert len(rows) == 10, f"Expected 10 rows, got {len(rows)}"
            
            # Check row 0
            row0 = rows[0]
            assert float(row0[header.index("gt_x")]) == 320.0
            assert float(row0[header.index("err_track_px")]) == 0.0
            assert int(row0[header.index("lock_status")]) == 1

            # Check row 5 (odd index -> is_locked is False)
            row5 = rows[5]
            assert float(row5[header.index("gt_x")]) == 325.0
            assert int(row5[header.index("lock_status")]) == 0
            assert int(row5[header.index("coast_frames")]) == 5

    def test_flush_behavior(self, temp_session_dir):
        sm = SessionManager(base_dir=temp_session_dir)
        logger = PerformanceLogger(session_manager=sm)
        logger.start()

        # Writing 65 frames to trigger periodic flush at frame 60
        for i in range(65):
            logger.record(
                gt_pos=(320, 240), det_pos=(320, 240), est_pos=(320, 240),
                pred_pos=(320, 240), err_track_px=0.5, err_gt_px=0.5,
                err_deg=0.01, fps=60.0, is_locked=True, coast_frames=0,
                pid_pan=0.0, pid_tilt=0.0, turb_level=0.0, vib_level=0.0, noise_level=0.0
            )

        assert logger._frame_count == 65
        logger.stop()

        with open(sm.log_path, "r") as f:
            lines = f.readlines()
            # Header + 65 data rows = 66 lines
            assert len(lines) == 66
