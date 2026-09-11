"""Pure (torch-free) color palette extraction for Rennart nodes.

Houses the k-means + Delta-E dedup core so it can be reused by the ComfyUI
nodes and by standalone tooling without importing torch. Inputs/outputs are
plain PIL images and hex string lists.

Also exposes four alternative palette-extraction strategies tuned for
different failure modes (rare accents, diverse spread, background + accent,
hue-based separation). The original sklearn KMeans + Delta-E path is kept
unchanged as `extract_palette`.

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

#: Working resolution for clustering. Larger keeps small accents more vivid
#: (less downscale blending), at a roughly linear cost in k-means time.
#: 256 is a good balance; 512 is noticeably slower on CPU.
RESIZE_DIM = 256


# ---------------------------------------------------------------------------
# Original method: sklearn KMeans + Delta-E dedup (unchanged).
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Shared helpers for the alternative methods.
# ---------------------------------------------------------------------------

def _dedupe_delta_e(rgb_colors, min_delta_e: float):
    """Filter colors so no two are within min_delta_e (LAB). Preserves order."""
    survivors_rgb = []
    survivors_lab = []
    for rgb in rgb_colors:
        lab = rgb_to_lab(np.asarray(rgb, dtype=np.float64))
        if any(delta_e(lab, kept) < min_delta_e for kept in survivors_lab):
            continue
        survivors_rgb.append(np.asarray(rgb, dtype=np.float64))
        survivors_lab.append(lab)
    return survivors_rgb


def _prepare_pixels(pil_image: Image.Image) -> np.ndarray:
    """Same preprocessing as the original method: RGB, RESIZE_DIM, float64 (N,3)."""
    small = pil_image.convert("RGB").resize((RESIZE_DIM, RESIZE_DIM))
    return np.asarray(small, dtype=np.float64).reshape(-1, 3)


def _quantize(pixels: np.ndarray, bits: int = 5) -> np.ndarray:
    """Reduce each channel to `bits` bits and return integer keys (N,)."""
    shift = 8 - bits
    q = (pixels.astype(np.uint16) >> shift).astype(np.int64)
    return q[:, 0] * (1 << (2 * bits)) + q[:, 1] * (1 << bits) + q[:, 2]


def _rgb_to_hsv_numpy(rgb: np.ndarray) -> np.ndarray:
    """Vectorized RGB->HSV. rgb is (N,3) in 0-255, returns (N,3) with H in [0,1), S,V in [0,1]."""
    rgb = np.asarray(rgb, dtype=np.float64) / 255.0
    maxc = np.max(rgb, axis=1)
    minc = np.min(rgb, axis=1)
    delta = maxc - minc
    v = maxc
    s = np.where(maxc > 0.0, delta / np.maximum(maxc, 1e-12), 0.0)

    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    h = np.zeros_like(r)
    mask = delta > 1e-12
    which = np.argmax(rgb, axis=1)

    rm = mask & (which == 0)
    gm = mask & (which == 1)
    bm = mask & (which == 2)

    h[rm] = ((g[rm] - b[rm]) / delta[rm]) % 6.0
    h[gm] = ((b[gm] - r[gm]) / delta[gm]) + 2.0
    h[bm] = ((r[bm] - g[bm]) / delta[bm]) + 4.0
    h = h / 6.0

    return np.stack([h, s, v], axis=1)


# ---------------------------------------------------------------------------
# Method 2: Weighted frequency.
#
# Idea: pixels whose (quantized) color is rare get more weight in the k-means
# fit. That way a small bright accent can hold its own against a large boring
# background. Weight goes as 1/sqrt(freq_of_bucket): a bucket with 10000 px
# still outweighs one with 1 px, but not by 10000x — only by 100x.
# ---------------------------------------------------------------------------

def _extract_weighted_frequency(pixels, num_colors, min_delta_e, bits: int = 5):
    if len(pixels) == 0:
        return []

    keys = _quantize(pixels, bits)
    _unique, inverse, counts = np.unique(keys, return_inverse=True, return_counts=True)
    # np.unique may return inverse with shape (N,1) in newer numpy; flatten.
    inverse = inverse.ravel()

    freq_per_pixel = counts[inverse].astype(np.float64)
    weights = 1.0 / np.sqrt(freq_per_pixel)

    n_clusters = max(1, min(num_colors, len(np.unique(inverse))))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=4)
    labels = kmeans.fit_predict(pixels, sample_weight=weights)
    centroids = kmeans.cluster_centers_

    # Order by *weighted* population so accents rise a little in the list.
    weighted_counts = np.bincount(labels, weights=weights, minlength=n_clusters)
    order = np.argsort(-weighted_counts)
    centroids = centroids[order]

    survivors = _dedupe_delta_e(centroids, min_delta_e)
    return [rgb_to_hex(rgb) for rgb in survivors]


def extract_palette_weighted_frequency(pil_image, num_colors, min_delta_e):
    """K-means with per-pixel weights that favour rare colors. Best for accents."""
    pixels = _prepare_pixels(pil_image)
    return _extract_weighted_frequency(pixels, num_colors, min_delta_e)


# ---------------------------------------------------------------------------
# Method 3: Farthest Point Sampling.
#
# Idea: k-means minimizes coverage error, which sacrifices rare colors. FPS
# does the opposite — it greedily picks colors that are as far as possible from
# everything already chosen. A tiny bright accent, being far from the
# background palette, wins a slot by construction. Noise is filtered by
# requiring each candidate bucket to hold at least a small fraction of pixels.
# ---------------------------------------------------------------------------

def _extract_farthest_point(pixels, num_colors, min_delta_e,
                            bits: int = 5, min_pop_frac: float = 0.0005):
    if len(pixels) == 0:
        return []

    keys = _quantize(pixels, bits)
    _unique, inverse, counts = np.unique(keys, return_inverse=True, return_counts=True)
    inverse = inverse.ravel()
    n_buckets = len(counts)

    # Representative color per bucket (mean of its pixels).
    bucket_means = np.zeros((n_buckets, 3), dtype=np.float64)
    for c in range(3):
        bucket_means[:, c] = np.bincount(inverse, weights=pixels[:, c], minlength=n_buckets)
    bucket_means /= counts[:, None]

    # Drop pure-noise buckets.
    min_count = max(1, int(min_pop_frac * len(pixels)))
    keep = counts >= min_count
    if not keep.any():
        keep = np.ones(n_buckets, dtype=bool)
    means = bucket_means[keep]
    cnts = counts[keep].astype(np.float64)

    n_pick = min(num_colors, len(means))
    if n_pick == 0:
        return []

    # First pick: the most frequent color (we still want a familiar anchor).
    first = int(np.argmax(cnts))
    selected = [first]
    dist = np.linalg.norm(means - means[first], axis=1)

    # Weight the "farness" score mildly by frequency so we don't chase noise.
    weight = 1.0 + np.log(cnts)

    for _ in range(n_pick - 1):
        score = dist * weight
        score[selected] = -1.0
        nxt = int(np.argmax(score))
        if score[nxt] <= 0.0:
            break
        selected.append(nxt)
        new_dist = np.linalg.norm(means - means[nxt], axis=1)
        dist = np.minimum(dist, new_dist)

    survivors = _dedupe_delta_e(means[selected], min_delta_e)
    return [rgb_to_hex(rgb) for rgb in survivors]


def extract_palette_farthest_point(pil_image, num_colors, min_delta_e):
    """Farthest Point Sampling. Best for maximally diverse palettes."""
    pixels = _prepare_pixels(pil_image)
    return _extract_farthest_point(pixels, num_colors, min_delta_e)


# ---------------------------------------------------------------------------
# Method 4: Two-pass background + accent.
#
# Idea: run k-means with k-1 clusters to cover the background, then look at the
# pixels that are worst explained by that palette, and cluster *those* into the
# last slot(s). A red car on a grey street is exactly the "worst explained"
# population, so it gets a dedicated slot instead of being averaged away.
# ---------------------------------------------------------------------------

def _extract_two_pass(pixels, num_colors, min_delta_e, accent_frac: float = 0.20):
    if len(pixels) == 0:
        return []
    if num_colors < 2:
        return palette_from_pixels(pixels, num_colors, min_delta_e)

    k_bg = max(1, num_colors - 1)
    bg_centroids, _bg_counts = clusters_from_pixels(pixels, k_bg)

    # Residual per pixel = distance to its nearest background centroid.
    diff = pixels[:, None, :] - bg_centroids[None, :, :]
    dists = np.linalg.norm(diff, axis=2)
    min_dists = dists.min(axis=1)

    # Top fraction by residual -> candidate accents.
    n_top = max(num_colors * 10, int(accent_frac * len(pixels)))
    n_top = min(n_top, len(pixels))
    if n_top <= 0:
        survivors = _dedupe_delta_e(bg_centroids, min_delta_e)
        return [rgb_to_hex(rgb) for rgb in survivors]

    if n_top >= len(pixels):
        accent_pixels = pixels
    else:
        top_idx = np.argpartition(-min_dists, n_top - 1)[:n_top]
        accent_pixels = pixels[top_idx]

    n_accent = max(1, num_colors - k_bg)
    if len(accent_pixels) >= n_accent:
        kmeans = KMeans(n_clusters=n_accent, random_state=42, n_init=4)
        kmeans.fit(accent_pixels)
        accent_centroids = kmeans.cluster_centers_
    else:
        accent_centroids = accent_pixels.mean(axis=0, keepdims=True)

    combined = np.vstack([bg_centroids, accent_centroids])
    survivors = _dedupe_delta_e(combined, min_delta_e)
    return [rgb_to_hex(rgb) for rgb in survivors]


def extract_palette_two_pass(pil_image, num_colors, min_delta_e):
    """Two-pass background + accent. Best for landscapes with one strong accent."""
    pixels = _prepare_pixels(pil_image)
    return _extract_two_pass(pixels, num_colors, min_delta_e)


# ---------------------------------------------------------------------------
# Method 5: Hue peaks (HSB).
#
# Idea: split the image into "colorful" (any real chroma) and "neutral" pixels.
# Inside the colorful half, build a hue histogram weighted so that saturated
# pixels count for more than bright ones (S^1.5 * V^0.5), then find peaks.
# The crucial trick is ranking peaks by *sharpness* (peak height divided by
# the highest of the two basin minima within a window) rather than by absolute
# height: a narrow accent peak in an otherwise flat hue region scores far
# higher than a broad, massive but smooth background peak. That is what
# surfaces a small red car against a green/beige cityscape.
# ---------------------------------------------------------------------------

def _extract_hue_peaks(pixels, num_colors, min_delta_e,
                       hue_bins: int = 72, min_sat: float = 0.08,
                       min_val: float = 0.05):
    if len(pixels) == 0:
        return []

    hsv = _rgb_to_hsv_numpy(pixels)
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]

    colorful_mask = (s >= min_sat) & (v >= min_val)
    n_colorful = int(colorful_mask.sum())
    if n_colorful == 0:
        # No chroma at all — hue peaks have nothing to work with.
        return palette_from_pixels(pixels, num_colors, min_delta_e)

    s_col = s[colorful_mask]
    v_col = v[colorful_mask]
    # Saturation matters more than brightness: a deep saturated red must not
    # lose to a washed-out pastel just because the pastel is brighter.
    w = (s_col ** 1.5) * (v_col ** 0.5)
    h_col = h[colorful_mask]
    px_col = pixels[colorful_mask]

    hist, _edges = np.histogram(h_col, bins=hue_bins, range=(0.0, 1.0), weights=w)

    # Very light circular smoothing: removes single-bin noise without
    # flattening narrow peaks.
    kernel = np.array([1.0, 2.0, 1.0], dtype=np.float64)
    kernel /= kernel.sum()
    padded = np.concatenate([hist[-1:], hist, hist[:1]])
    hist_s = np.convolve(padded, kernel, mode="same")[1:-1]

    # Local maxima (circular).
    peaks = []
    for i in range(hue_bins):
        left = hist_s[(i - 1) % hue_bins]
        right = hist_s[(i + 1) % hue_bins]
        if hist_s[i] > left and hist_s[i] >= right and hist_s[i] > 0.0:
            peaks.append(i)

    if not peaks:
        return palette_from_pixels(pixels, num_colors, min_delta_e)

    # Score each peak by sharpness = height / max(basin minima within a window).
    # Broad background peaks have a high basin, so their sharpness is ~1.
    # Narrow accent peaks have a low basin, so their sharpness is huge.
    window = max(2, hue_bins // 12)
    scored = []
    for i in peaks:
        left_min = min(hist_s[(i - k) % hue_bins] for k in range(1, window + 1))
        right_min = min(hist_s[(i + k) % hue_bins] for k in range(1, window + 1))
        basin = max(left_min, right_min)
        if hist_s[i] <= basin:
            continue
        sharpness = hist_s[i] / (basin + 1e-9)
        scored.append((i, float(hist_s[i]), float(sharpness)))

    # Drop peaks whose absolute weight is negligible; they are noise.
    scored = [t for t in scored if t[1] >= 1.0]
    if not scored:
        return palette_from_pixels(pixels, num_colors, min_delta_e)

    scored.sort(key=lambda t: -t[2])
    top = scored[:num_colors]

    bin_width = 1.0 / hue_bins
    colors = []
    for peak_idx, _height, _sharp in top:
        center = (peak_idx + 0.5) * bin_width
        delta = np.abs(h_col - center)
        delta = np.minimum(delta, 1.0 - delta)
        in_bin = delta <= window * bin_width * 0.5
        if not in_bin.any():
            continue
        # Favour the vivid representative of the peak's neighbourhood.
        ww = s_col[in_bin] ** 2
        denom = max(float(ww.sum()), 1e-9)
        avg = (px_col[in_bin] * ww[:, None]).sum(axis=0) / denom
        colors.append(avg)

    # Fill remaining slots from neutral pixels, so a mostly-grey image does
    # not end up with a palette of near-identical hues.
    if len(colors) < num_colors:
        neutral = pixels[~colorful_mask]
        remaining = num_colors - len(colors)
        if remaining > 0 and len(neutral) >= remaining:
            kmeans = KMeans(n_clusters=remaining, random_state=42, n_init=4)
            kmeans.fit(neutral)
            for c in kmeans.cluster_centers_:
                colors.append(c)

    if not colors:
        return palette_from_pixels(pixels, num_colors, min_delta_e)

    survivors = _dedupe_delta_e(np.asarray(colors), min_delta_e)
    return [rgb_to_hex(rgb) for rgb in survivors]


def extract_palette_hue_peaks(pil_image, num_colors, min_delta_e):
    """Hue-histogram peaks in HSB. Best for images with distinct saturated hues."""
    pixels = _prepare_pixels(pil_image)
    return _extract_hue_peaks(pixels, num_colors, min_delta_e)