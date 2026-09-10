"""Color space conversion and perceptual distance helpers.

Provides RGB<->LAB conversion, CIE76 Delta-E distance in LAB space, and
hex<->RGB helpers used throughout the palette extraction nodes.
"""

import numpy as np


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert a hex string like '#FF5733' or 'FF5733' to an (R, G, B) tuple of ints 0-255."""
    h = hex_color.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb) -> str:
    """Convert an (R, G, B) tuple/array of ints or floats (0-255) to a '#RRGGBB' hex string."""
    r, g, b = (int(round(c)) for c in rgb)
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def _srgb_to_linear(c: np.ndarray) -> np.ndarray:
    """Apply sRGB inverse gamma to normalized (0-1) channel values."""
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rgb_to_lab(rgb) -> np.ndarray:
    """Convert RGB (0-255, single color or Nx3 array) to CIE LAB (D65 illuminant).

    Returns an array of the same leading shape with the last axis being [L, a, b].
    """
    arr = np.asarray(rgb, dtype=np.float64)
    single = arr.ndim == 1
    if single:
        arr = arr.reshape(1, 3)

    rgb_norm = arr / 255.0
    rgb_lin = _srgb_to_linear(rgb_norm)

    # sRGB -> XYZ (D65)
    r = rgb_lin[:, 0]
    g = rgb_lin[:, 1]
    b = rgb_lin[:, 2]

    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    # Normalize by D65 white point reference
    xn, yn, zn = 0.95047, 1.00000, 1.08883
    x /= xn
    y /= yn
    z /= zn

    def f(t):
        delta = 6.0 / 29.0
        return np.where(t > delta ** 3, np.cbrt(t), t / (3 * delta ** 2) + 4.0 / 29.0)

    fx, fy, fz = f(x), f(y), f(z)

    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b_ = 200.0 * (fy - fz)

    lab = np.stack([L, a, b_], axis=-1)
    return lab[0] if single else lab


def delta_e(lab1, lab2) -> float:
    """CIE76 Delta-E perceptual distance between two LAB colors (euclidean distance in LAB space)."""
    l1 = np.asarray(lab1, dtype=np.float64)
    l2 = np.asarray(lab2, dtype=np.float64)
    return float(np.sqrt(np.sum((l1 - l2) ** 2)))


def rgb_to_hsl(rgb):
    """Convert an (R, G, B) tuple/array (0-255) to (H, S, L), each in 0-1."""
    r, g, b = (float(c) / 255.0 for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    lightness = (mx + mn) / 2.0
    if mx == mn:
        return 0.0, 0.0, lightness
    d = mx - mn
    saturation = d / (2.0 - mx - mn) if lightness > 0.5 else d / (mx + mn)
    if mx == r:
        hue = ((g - b) / d) % 6.0
    elif mx == g:
        hue = (b - r) / d + 2.0
    else:
        hue = (r - g) / d + 4.0
    return hue / 6.0, saturation, lightness
