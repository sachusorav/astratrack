"""
ASTRATRACK — Constants

Color definitions, default values, and physical constants used across modules.
"""

# --- Colors (BGR for OpenCV) ---
COLOR_BEACON = (0, 255, 100)        # Bright green beacon
COLOR_BEACON_GLOW = (0, 180, 60)    # Beacon outer glow
COLOR_FOV_RECT = (255, 255, 0)      # Cyan FOV rectangle
COLOR_DETECTION = (0, 255, 255)     # Yellow detection circle
COLOR_ESTIMATE = (255, 0, 255)      # Magenta Kalman estimate
COLOR_PREDICTION = (255, 255, 255)  # White prediction path
COLOR_ERROR_LINE = (0, 0, 255)      # Red error line
COLOR_CROSSHAIR = (100, 100, 100)   # Gray crosshair at FOV center
COLOR_WORLD_BG = (10, 10, 30)       # Dark background
COLOR_TEXT = (220, 220, 220)         # Light text overlay
COLOR_LOCK_ON = (0, 255, 0)         # Green — locked
COLOR_LOCK_OFF = (0, 0, 255)        # Red — lost

# --- Colors (RGBA for Dear PyGui, 0–255 int) ---
DPGC_GREEN = (0, 255, 100, 255)
DPGC_RED = (255, 80, 80, 255)
DPGC_YELLOW = (255, 255, 0, 255)
DPGC_CYAN = (0, 255, 255, 255)
DPGC_MAGENTA = (255, 0, 255, 255)
DPGC_WHITE = (220, 220, 220, 255)
DPGC_DIM = (120, 120, 120, 255)
DPGC_BG_DARK = (15, 15, 30, 255)
DPGC_PANEL_BG = (25, 28, 40, 255)
DPGC_ACCENT = (0, 200, 255, 255)

# --- Defaults ---
DEFAULT_FPS = 60
DEFAULT_DT = 1.0 / DEFAULT_FPS

# --- UI Tags (Dear PyGui item identifiers) ---
TAG_SIM_TEXTURE = "sim_texture"
TAG_MAIN_WINDOW = "main_window"
TAG_METRICS_WINDOW = "metrics_window"
TAG_CONTROL_WINDOW = "control_window"
TAG_PLOT_WINDOW = "plot_window"
