"""
ASTRATRACK — Session Manager

Creates timestamped session folders for organizing log files and metadata.
"""

import os
import json
from datetime import datetime


class SessionManager:
    """
    Manages session folders for performance logging.

    Each session creates a timestamped directory containing:
        - metadata.json — session configuration and start time
        - tracking_log.csv — per-frame performance data
    """

    def __init__(self, base_dir: str = "sessions"):
        """
        Initialize session manager.

        Args:
            base_dir: Base directory for all sessions.
        """
        self.base_dir = base_dir
        self.session_dir = None
        self.session_id = None

    def start_session(self, config_dict: dict = None) -> str:
        """
        Create a new session directory.

        Args:
            config_dict: Optional configuration snapshot to save as metadata.

        Returns:
            Path to the session directory.
        """
        self.session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_dir = os.path.join(self.base_dir, self.session_id)
        os.makedirs(self.session_dir, exist_ok=True)

        # Write metadata
        metadata = {
            "session_id": self.session_id,
            "start_time": datetime.now().isoformat(),
            "config": config_dict or {},
        }
        meta_path = os.path.join(self.session_dir, "metadata.json")
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)

        return self.session_dir

    @property
    def log_path(self) -> str:
        """Path to the CSV log file for the current session."""
        if self.session_dir is None:
            return "tracking_log.csv"
        return os.path.join(self.session_dir, "tracking_log.csv")
