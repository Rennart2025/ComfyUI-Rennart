"""Pure (torch-free) color palette extraction for Rennart nodes.

Houses the k-means + Delta-E dedup core so it can be reused by the ComfyUI
nodes and by standalone tooling without importing torch. Inputs/outputs are
plain PIL images and hex string lists.

Originally adapted from Ideogram's utils/extract.py; renamed to
color_palette_extract.py for clarity. Internal imports are relative and
therefore unaffected by the rename.
"""

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

try:
    from .color_utils import rgb_to_hex, rgb_to_lab, delta_e
except ImportError:
    from color_utils import rgb_to_hex, rgb_to_lab, delta_e

RESIZE_DIM = 150


def clusters_from_pixels(pixels, num_colors: int):
    """Run k-means on a flat pixel array. Returns (centroids, counts) sorted by
    population descending.

    Args:
        pixels: an (N, 3) array of RGB values in 0-255.
        num_colors: target k-means cluster count.

    Returns:
        (centroids, counts) where centroids is a (k, 3) float array of RGB values
        and counts is a (k,) int array, both ordered most-populous first. Empty
        arrays when there are no pixels.
    """
    pixels = np.asarray(pixels, dtype=np.float64)
    if pixels.size == 0:
        return np.empty((0, 3)), np.empty((0,), dtype=int)
    pixels = pixels.reshape(-1, 3)

    unique_colors = np.unique(pixels, axis=0)
    n_clusters = max(1, min(num_colors, len(unique_colors)))

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=4)
    labels = kmeans.fit_predict(pixels)
    centroids = kmeans.cluster_centers_

    counts = np.bincount(labels, minlength=n_clusters)
    order = np.argsort(-counts)
    return centroids[order], counts[order]


def palette_from_pixels(pixels, num_colors: int, min_delta_e: float):
    """Run k-means + Delta-E dedup on a flat pixel array. Returns hex strings, dominant first.

    Args:
        pixels: an (N, 3) array of RGB values in 0-255.
        num_colors: target k-means cluster count (upper bound on returned colors).
        min_delta_e: minimum perceptual (LAB) distance required between kept colors.

    Returns:
        list of "#RRGGBB" hex strings ordered by prominence (most dominant first),
        deduplicated so no two are within min_delta_e of each other. Returns []
        when there are no pixels. May return fewer than num_colors; never more.
    """
    centroids, _counts = clusters_from_pixels(pixels, num_colors)

    survivors_rgb = []
    survivors_lab = []
    for centroid_rgb in centroids:  # already ordered most-populous first
        centroid_lab = rgb_to_lab(centroid_rgb)
        if any(delta_e(centroid_lab, kept) < min_delta_e for kept in survivors_lab):
            continue
        survivors_rgb.append(centroid_rgb)
        survivors_lab.append(centroid_lab)

    return [rgb_to_hex(rgb) for rgb in survivors_rgb]


def extract_palette(pil_image: Image.Image, num_colors: int, min_delta_e: float):
    """Run k-means extraction + Delta-E dedup on a full image. Returns hex strings, dominant first.

    Args:
        pil_image: source image (any mode; converted to RGB internally).
        num_colors: target k-means cluster count (upper bound on returned colors).
        min_delta_e: minimum perceptual (LAB) distance required between kept colors.

    Returns:
        list of "#RRGGBB" hex strings ordered by prominence (most dominant first),
        deduplicated so no two are within min_delta_e of each other. May return
        fewer than num_colors; never more.
    """
    small = pil_image.convert("RGB").resize((RESIZE_DIM, RESIZE_DIM))
    pixels = np.asarray(small, dtype=np.float64).reshape(-1, 3)
    return palette_from_pixels(pixels, num_colors, min_delta_e)