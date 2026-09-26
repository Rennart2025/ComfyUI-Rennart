import cv2
import numpy as np
import torch
from skimage.transform import PiecewiseAffineTransform, warp


class RennartPixelDriftFix:
    """
    Rennart Pixel Drift Fix

    Aligns an edited image back to the geometry of the source image
    using feature matching and homography-based warping.

    Two modes:
        flat_4_points - fast global perspective correction
        mesh          - experimental dense non-linear correction
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source_image": (
                    "IMAGE",
                ),
                "edited_image": (
                    "IMAGE",
                ),
                "method": (
                    [
                        "flat_4_points",
                        "mesh",
                    ],
                    {
                        "default": "flat_4_points",
                        "tooltip": (
                            "flat_4_points gives better results and is faster. "
                            "Mesh is experimental."
                        ),
                    },
                ),
                "max_mesh_points": (
                    "INT",
                    {
                        "default": 400,
                        "min": 100,
                        "max": 10000,
                        "step": 100,
                        "display": "number",
                        "tooltip": (
                            "Only used when method is set to 'mesh'. "
                            "Higher values increase alignment accuracy but "
                            "take longer. 400 = good/fast, 10000 = best quality."
                        ),
                    },
                ),
            },
        }

    RETURN_TYPES = (
        "IMAGE",
    )

    RETURN_NAMES = (
        "fixed_image",
    )

    FUNCTION = "fix_pixel_drift"

    CATEGORY = "Rennart/Image"

    def fix_pixel_drift(
        self,
        source_image,
        edited_image,
        method,
        max_mesh_points,
    ):
        """
        Fix pixel drift between source and edited images.

        ComfyUI IMAGE tensors:
            [B, H, W, C]
            float32
            range 0.0 - 1.0
            RGB

        The algorithm:
            1. Convert images to OpenCV BGR uint8.
            2. Detect SIFT features.
            3. Match features with BFMatcher.
            4. Filter matches using Lowe's ratio test.
            5. Estimate homography using RANSAC.
            6. Warp edited image back to source geometry.
            7. Optionally apply a Piecewise Affine mesh correction.
            8. Convert result back to ComfyUI IMAGE tensor.
        """

        # ---------------------------------------------------------
        # Validate batch sizes
        # ---------------------------------------------------------

        b1, h1, w1, c1 = source_image.shape
        b2, h2, w2, c2 = edited_image.shape

        batch_size = min(b1, b2)

        output_tensors = []

        # ---------------------------------------------------------
        # Process every image in the batch
        # ---------------------------------------------------------

        for i in range(batch_size):

            # -----------------------------------------------------
            # Convert ComfyUI tensors to uint8 RGB
            # -----------------------------------------------------

            img_orig_rgb = (
                source_image[i]
                .cpu()
                .numpy()
                * 255.0
            ).clip(0, 255).astype(np.uint8)

            img_mod_rgb = (
                edited_image[i]
                .cpu()
                .numpy()
                * 255.0
            ).clip(0, 255).astype(np.uint8)

            # -----------------------------------------------------
            # RGB -> BGR for OpenCV
            # -----------------------------------------------------

            img_orig = cv2.cvtColor(
                img_orig_rgb,
                cv2.COLOR_RGB2BGR,
            )

            img_mod = cv2.cvtColor(
                img_mod_rgb,
                cv2.COLOR_RGB2BGR,
            )

            # -----------------------------------------------------
            # Source dimensions define final output dimensions
            # -----------------------------------------------------

            height, width = img_orig.shape[:2]

            # -----------------------------------------------------
            # Convert to grayscale
            # -----------------------------------------------------

            gray_orig = cv2.cvtColor(
                img_orig,
                cv2.COLOR_BGR2GRAY,
            )

            gray_mod = cv2.cvtColor(
                img_mod,
                cv2.COLOR_BGR2GRAY,
            )

            # -----------------------------------------------------
            # SIFT
            #
            # Parameters are kept compatible with the original
            # PixelDriftFix implementation.
            # -----------------------------------------------------

            sift = cv2.SIFT_create(
                nfeatures=0,
                nOctaveLayers=3,
                contrastThreshold=0.01,
                edgeThreshold=20,
                sigma=1.6,
            )

            kp_orig, des_orig = sift.detectAndCompute(
                gray_orig,
                None,
            )

            kp_mod, des_mod = sift.detectAndCompute(
                gray_mod,
                None,
            )

            # -----------------------------------------------------
            # Check that enough features were detected
            # -----------------------------------------------------

            if (
                des_orig is None
                or des_mod is None
                or len(kp_orig) < 10
                or len(kp_mod) < 10
            ):
                print(
                    "[Rennart Pixel Drift Fix] "
                    f"Warning: Not enough features found in batch {i}. "
                    "Passing edited image through."
                )

                output_tensors.append(
                    edited_image[i]
                )

                continue

            # -----------------------------------------------------
            # Feature matching
            # -----------------------------------------------------

            bf = cv2.BFMatcher()

            matches = bf.knnMatch(
                des_mod,
                des_orig,
                k=2,
            )

            # -----------------------------------------------------
            # Lowe ratio test
            # -----------------------------------------------------

            good_matches = []

            for match_pair in matches:

                if len(match_pair) != 2:
                    continue

                m, n = match_pair

                if m.distance < 0.80 * n.distance:
                    good_matches.append(m)

            # -----------------------------------------------------
            # Need enough matches for reliable homography
            # -----------------------------------------------------

            if len(good_matches) < 10:

                print(
                    "[Rennart Pixel Drift Fix] "
                    f"Warning: Too few good matches "
                    f"({len(good_matches)}) in batch {i}. "
                    "Passing edited image through."
                )

                output_tensors.append(
                    edited_image[i]
                )

                continue

            # -----------------------------------------------------
            # Extract matched coordinates
            #
            # pts_mod:
            #     coordinates in edited image
            #
            # pts_orig:
            #     corresponding coordinates in source image
            # -----------------------------------------------------

            pts_mod = np.float32(
                [
                    kp_mod[m.queryIdx].pt
                    for m in good_matches
                ]
            ).reshape(-1, 2)

            pts_orig = np.float32(
                [
                    kp_orig[m.trainIdx].pt
                    for m in good_matches
                ]
            ).reshape(-1, 2)

            # -----------------------------------------------------
            # Calculate homography using RANSAC
            # -----------------------------------------------------

            M, mask = cv2.findHomography(
                pts_mod,
                pts_orig,
                cv2.RANSAC,
                5.0,
            )

            if M is None or mask is None:

                print(
                    "[Rennart Pixel Drift Fix] "
                    f"Warning: Homography matrix computation "
                    f"failed in batch {i}."
                )

                output_tensors.append(
                    edited_image[i]
                )

                continue

            # -----------------------------------------------------
            # Keep only RANSAC inliers
            # -----------------------------------------------------

            inlier_mask = mask.ravel() == 1

            inliers_mod = pts_mod[inlier_mask]
            inliers_orig = pts_orig[inlier_mask]

            # -----------------------------------------------------
            # Check number of reliable static features
            # -----------------------------------------------------

            if len(inliers_mod) < 10:

                print(
                    "[Rennart Pixel Drift Fix] "
                    f"Warning: Too few static features "
                    f"({len(inliers_mod)}) found after RANSAC "
                    "filtering. Images should be similar."
                )

                output_tensors.append(
                    edited_image[i]
                )

                continue

            # -----------------------------------------------------
            # Global perspective correction
            #
            # This is always calculated because:
            #
            #   - flat_4_points uses it directly
            #   - mesh uses it as a fallback for invalid regions
            # -----------------------------------------------------

            global_warped = cv2.warpPerspective(
                img_mod,
                M,
                (width, height),
                borderMode=cv2.BORDER_REPLICATE,
            )

            # -----------------------------------------------------
            # METHOD: MESH
            # -----------------------------------------------------

            if method == "mesh":

                try:

                    # -------------------------------------------------
                    # Create rigid boundary anchor points
                    # -------------------------------------------------

                    edge_points = []

                    step_size = 30

                    # Top and bottom edges
                    for x in range(
                        0,
                        width,
                        step_size,
                    ):
                        edge_points.append(
                            [x, 0]
                        )

                        edge_points.append(
                            [x, height - 1]
                        )

                    # Left and right edges
                    for y in range(
                        0,
                        height,
                        step_size,
                    ):
                        edge_points.append(
                            [0, y]
                        )

                        edge_points.append(
                            [width - 1, y]
                        )

                    # Explicit corners
                    edge_points.extend(
                        [
                            [0, 0],
                            [width - 1, 0],
                            [0, height - 1],
                            [width - 1, height - 1],
                        ]
                    )

                    corners = np.array(
                        edge_points,
                        dtype=np.float32,
                    ).reshape(-1, 2)

                    # Remove duplicates
                    corners = np.unique(
                        corners,
                        axis=0,
                    )

                    # -------------------------------------------------
                    # Project boundary points using the global
                    # homography.
                    # -------------------------------------------------

                    corners_proj = cv2.perspectiveTransform(
                        corners.reshape(-1, 1, 2),
                        M,
                    ).reshape(-1, 2)

                    # Keep projected points inside the image
                    corners_proj[:, 0] = np.clip(
                        corners_proj[:, 0],
                        0,
                        width - 1,
                    )

                    corners_proj[:, 1] = np.clip(
                        corners_proj[:, 1],
                        0,
                        height - 1,
                    )

                    # -------------------------------------------------
                    # Combine feature points and boundary anchors
                    # -------------------------------------------------

                    final_mod = np.vstack(
                        [
                            inliers_mod,
                            corners,
                        ]
                    )

                    final_orig = np.vstack(
                        [
                            inliers_orig,
                            corners_proj,
                        ]
                    )

                    # -------------------------------------------------
                    # Limit number of mesh points
                    # -------------------------------------------------

                    if len(final_mod) > max_mesh_points:

                        idx = np.linspace(
                            0,
                            len(final_mod) - 1,
                            max_mesh_points,
                            dtype=int,
                        )

                        final_mod = final_mod[idx]
                        final_orig = final_orig[idx]

                    print(
                        "[Rennart Pixel Drift Fix] "
                        f"Using mesh with {len(final_mod)} points."
                    )

                    # -------------------------------------------------
                    # Create PiecewiseAffineTransform
                    #
                    # Different scikit-image versions expose
                    # different APIs, so support both.
                    # -------------------------------------------------

                    if hasattr(
                        PiecewiseAffineTransform,
                        "from_estimate",
                    ):

                        tform = (
                            PiecewiseAffineTransform.from_estimate(
                                final_orig,
                                final_mod,
                            )
                        )

                    else:

                        tform = PiecewiseAffineTransform()

                        tform.estimate(
                            final_orig,
                            final_mod,
                        )

                    # -------------------------------------------------
                    # Apply dense local warp
                    # -------------------------------------------------

                    local_warped_raw = warp(
                        img_mod,
                        tform,
                        output_shape=(
                            height,
                            width,
                        ),
                        order=1,
                        mode="edge",
                    )

                    local_warped = (
                        local_warped_raw * 255.0
                    ).clip(
                        0,
                        255,
                    ).astype(
                        np.uint8
                    )

                    # -------------------------------------------------
                    # Calculate coverage mask
                    #
                    # This determines which pixels were actually
                    # covered by the mesh transformation.
                    # -------------------------------------------------

                    coverage_input = np.ones(
                        (
                            height,
                            width,
                        ),
                        dtype=np.float32,
                    )

                    coverage_warped = warp(
                        coverage_input,
                        tform,
                        output_shape=(
                            height,
                            width,
                        ),
                        order=0,
                        cval=0,
                    )

                    valid_mesh_mask = (
                        coverage_warped > 0.5
                    )

                    # -------------------------------------------------
                    # Use mesh where valid.
                    # Fall back to global homography elsewhere.
                    # -------------------------------------------------

                    final_img = np.where(
                        valid_mesh_mask[:, :, None],
                        local_warped,
                        global_warped,
                    )

                except Exception as warp_error:

                    print(
                        "[Rennart Pixel Drift Fix] "
                        "Error during dense warping: "
                        f"{warp_error}. "
                        "Falling back to global homography."
                    )

                    final_img = global_warped

            # -----------------------------------------------------
            # METHOD: FLAT
            # -----------------------------------------------------

            else:

                print(
                    "[Rennart Pixel Drift Fix] "
                    "Using flat_4_points."
                )

                final_img = global_warped

            # -----------------------------------------------------
            # Convert BGR -> RGB
            # -----------------------------------------------------

            final_rgb = cv2.cvtColor(
                final_img,
                cv2.COLOR_BGR2RGB,
            )

            # -----------------------------------------------------
            # Convert uint8 image back to ComfyUI IMAGE tensor
            # -----------------------------------------------------

            out_tensor = (
                torch.from_numpy(
                    final_rgb
                ).float()
                / 255.0
            )

            output_tensors.append(
                out_tensor
            )

        # ---------------------------------------------------------
        # Restore batch dimension
        # ---------------------------------------------------------

        fixed_image_batch = torch.stack(
            output_tensors,
            dim=0,
        )

        return (
            fixed_image_batch,
        )


# ================================================================
# ComfyUI NODE REGISTRATION
# ================================================================

NODE_CLASS_MAPPINGS = {
    "RennartPixelDriftFix": RennartPixelDriftFix,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RennartPixelDriftFix": "Rennart Pixel Drift Fix",
}