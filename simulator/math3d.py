"""
ASTRATRACK — 3D Mathematics Module

Vector operations, rotation matrices, perspective projection, and coordinate
transformations for the 3D FSOC tracking simulator.

Coordinate convention (Y-up, right-handed):
    X → Right / East
    Y → Up
    Z → Forward / North (into scene)
"""

import numpy as np
from typing import Optional, Tuple


# ------------------------------------------------------------------ #
# Vector Utilities
# ------------------------------------------------------------------ #

def normalize(v: np.ndarray) -> np.ndarray:
    """Normalize a vector. Returns zero vector if input has zero length."""
    norm = np.linalg.norm(v)
    if norm < 1e-10:
        return np.zeros_like(v)
    return v / norm


def angle_between(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute the angle between two vectors in degrees."""
    n1 = normalize(v1)
    n2 = normalize(v2)
    dot = np.clip(np.dot(n1, n2), -1.0, 1.0)
    return float(np.degrees(np.arccos(dot)))


def spherical_to_cartesian(azimuth_deg: float, elevation_deg: float,
                           radius: float) -> np.ndarray:
    """
    Convert spherical coordinates to Cartesian (Y-up).

    Args:
        azimuth_deg: Horizontal angle from +Z axis (degrees).
        elevation_deg: Vertical angle above XZ plane (degrees).
        radius: Distance from origin.

    Returns:
        (x, y, z) position as numpy array.
    """
    az = np.radians(azimuth_deg)
    el = np.radians(elevation_deg)
    x = radius * np.cos(el) * np.sin(az)
    y = radius * np.sin(el)
    z = radius * np.cos(el) * np.cos(az)
    return np.array([x, y, z], dtype=np.float64)


# ------------------------------------------------------------------ #
# Rotation Matrices (3×3)
# ------------------------------------------------------------------ #

def rotation_x(angle_rad: float) -> np.ndarray:
    """3×3 rotation matrix around the X axis."""
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def rotation_y(angle_rad: float) -> np.ndarray:
    """3×3 rotation matrix around the Y axis."""
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def rotation_z(angle_rad: float) -> np.ndarray:
    """3×3 rotation matrix around the Z axis."""
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


# ------------------------------------------------------------------ #
# View & Projection Matrices (4×4)
# ------------------------------------------------------------------ #

def look_at_matrix(eye: np.ndarray, target: np.ndarray,
                   up: np.ndarray = None) -> np.ndarray:
    """
    Build a 4×4 view matrix (world → camera space).

    Args:
        eye: Camera position in world space (3,).
        target: Look-at target in world space (3,).
        up: World up vector (default: Y-up).

    Returns:
        4×4 view matrix (np.float64).
    """
    if up is None:
        up = np.array([0.0, 1.0, 0.0])

    forward = normalize(target - eye)
    right = normalize(np.cross(forward, up))

    # Handle degenerate case (looking straight up/down)
    if np.linalg.norm(right) < 1e-6:
        alt_up = np.array([0.0, 0.0, 1.0])
        right = normalize(np.cross(forward, alt_up))

    up_actual = np.cross(right, forward)

    view = np.eye(4, dtype=np.float64)
    view[0, :3] = right
    view[1, :3] = up_actual
    view[2, :3] = -forward
    view[:3, 3] = np.array([
        -np.dot(right, eye),
        -np.dot(up_actual, eye),
        np.dot(forward, eye),
    ])
    return view


def perspective_proj(fov_deg: float, aspect: float,
                     near: float = 0.1, far: float = 10000.0) -> np.ndarray:
    """
    Build a 4×4 perspective projection matrix.

    Args:
        fov_deg: Vertical field of view in degrees.
        aspect: Width / height aspect ratio.
        near: Near clipping distance.
        far: Far clipping distance.

    Returns:
        4×4 projection matrix (np.float64).
    """
    fov_rad = np.radians(fov_deg)
    f = 1.0 / np.tan(fov_rad / 2.0)

    proj = np.zeros((4, 4), dtype=np.float64)
    proj[0, 0] = f / aspect
    proj[1, 1] = f
    proj[2, 2] = (far + near) / (near - far)
    proj[2, 3] = (2.0 * far * near) / (near - far)
    proj[3, 2] = -1.0
    return proj


# ------------------------------------------------------------------ #
# 3D → 2D Projection
# ------------------------------------------------------------------ #

def project_point(point: np.ndarray, view: np.ndarray, proj: np.ndarray,
                  screen_w: int, screen_h: int) -> Optional[Tuple[int, int, float]]:
    """
    Project a 3D world point to 2D screen coordinates.

    Args:
        point: 3D position (3,).
        view: 4×4 view matrix.
        proj: 4×4 projection matrix.
        screen_w: Viewport width in pixels.
        screen_h: Viewport height in pixels.

    Returns:
        (screen_x, screen_y, depth) or None if behind camera / degenerate.
    """
    p_h = np.array([point[0], point[1], point[2], 1.0], dtype=np.float64)

    # World → Camera space
    p_view = view @ p_h

    # Cull: behind camera (camera looks down -Z in view space)
    if p_view[2] > -0.01:
        return None

    # Camera → Clip space
    p_clip = proj @ p_view

    if abs(p_clip[3]) < 1e-10:
        return None

    # Perspective divide → NDC [-1, 1]
    ndc_x = p_clip[0] / p_clip[3]
    ndc_y = p_clip[1] / p_clip[3]
    depth = p_clip[2] / p_clip[3]

    # NDC → Screen pixels (Y flipped)
    sx = int((ndc_x + 1.0) * 0.5 * screen_w)
    sy = int((1.0 - ndc_y) * 0.5 * screen_h)

    return (sx, sy, depth)


def project_line(p1: np.ndarray, p2: np.ndarray,
                 view: np.ndarray, proj: np.ndarray,
                 screen_w: int, screen_h: int
                 ) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
    """
    Project a 3D line segment to 2D screen endpoints.

    Returns:
        ((x1, y1), (x2, y2)) or None if either endpoint is behind camera.
    """
    s1 = project_point(p1, view, proj, screen_w, screen_h)
    s2 = project_point(p2, view, proj, screen_w, screen_h)

    if s1 is None or s2 is None:
        return None

    return ((s1[0], s1[1]), (s2[0], s2[1]))


def clamp_to_screen(x: int, y: int, w: int, h: int) -> Tuple[int, int]:
    """Clamp screen coordinates to viewport bounds."""
    return (max(0, min(w - 1, x)), max(0, min(h - 1, y)))
