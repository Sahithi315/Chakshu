"""Advanced document image preprocessing pipeline for handwritten prescriptions and medical reports.

Provides orientation correction, deskewing, shadow and noise removal, contrast enhancement,
adaptive thresholding, and handwriting feature detection using OpenCV and Pillow.
Preserves original documents untouched while generating optimized representations for OCR.
"""
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Union, List
import numpy as np
import cv2
from PIL import Image, ImageOps, ImageEnhance
import pytesseract


def pil_to_cv(image: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV BGR (or Grayscale) numpy array."""
    if image.mode == "L":
        return np.array(image, dtype=np.uint8)
    if image.mode != "RGB":
        image = image.convert("RGB")
    rgb = np.array(image, dtype=np.uint8)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def cv_to_pil(cv_img: np.ndarray) -> Image.Image:
    """Convert OpenCV numpy array (BGR or Grayscale) to PIL Image."""
    if len(cv_img.shape) == 2:
        return Image.fromarray(cv_img, mode="L")
    rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb, mode="RGB")


def to_grayscale(img: Union[np.ndarray, Image.Image]) -> np.ndarray:
    """Convert any input image to a 2D grayscale numpy array."""
    if isinstance(img, Image.Image):
        return np.array(img.convert("L"), dtype=np.uint8)
    if len(img.shape) == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img.copy()


def correct_exif_orientation(image: Image.Image) -> Image.Image:
    """Correct orientation from EXIF metadata (camera/phone uploads)."""
    try:
        return ImageOps.exif_transpose(image)
    except Exception:
        return image


def detect_and_correct_rotation(image: Image.Image) -> Tuple[Image.Image, int]:
    """
    Detect document rotation (0, 90, 180, 270 degrees) using Tesseract OSD and correct it.
    Returns the rotated PIL Image and the angle applied.
    """
    rot_angle = 0
    try:
        # Check orientation via Tesseract OSD
        osd = pytesseract.image_to_osd(image)
        for line in osd.splitlines():
            if line.startswith("Rotate:"):
                rot_angle = int(line.split(":")[1].strip())
                break
    except Exception:
        rot_angle = 0

    if rot_angle == 90:
        return image.rotate(270, expand=True), 90
    elif rot_angle == 180:
        return image.rotate(180, expand=True), 180
    elif rot_angle == 270:
        return image.rotate(90, expand=True), 270

    return image, 0


def correct_skew(gray: np.ndarray, max_angle: float = 45.0) -> Tuple[np.ndarray, float]:
    """
    Detect text baseline skew using minAreaRect on thresholded text pixels and deskew.
    Constrained to [-max_angle, max_angle] to avoid flipping document axes.
    """
    try:
        # Invert Otsu threshold: text is white (255), background is black (0)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 100:
            return gray.copy(), 0.0

        angle = cv2.minAreaRect(coords)[-1]
        # Normalize angle to [-45, 45]
        if angle < -45.0:
            angle = -(90.0 + angle)
        elif angle > 45.0:
            angle = 90.0 - angle

        # Ignore tiny imperceptible skews
        if abs(angle) < 0.5 or abs(angle) > max_angle:
            return gray.copy(), 0.0

        h, w = gray.shape[:2]
        center = (w // 2, h // 2)
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        deskewed = cv2.warpAffine(
            gray, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
        return deskewed, float(angle)
    except Exception:
        return gray.copy(), 0.0


def remove_shadows_and_noise(gray: np.ndarray) -> np.ndarray:
    """
    Remove uneven illumination, camera flash gradients, and shadows using morphological
    background division, followed by edge-preserving bilateral filtering.
    """
    try:
        # Estimate background illumination with large morphological dilation
        kernel_size = 25
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        dilated = cv2.dilate(gray, kernel)
        bg = cv2.medianBlur(dilated, 21)

        # Flatten shadows by computing difference or division
        diff = 255 - cv2.absdiff(gray, bg)
        normalized = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)

        # Bilateral filter to remove sensor/paper grain while keeping crisp ink lines
        denoised = cv2.bilateralFilter(normalized, d=7, sigmaColor=40, sigmaSpace=40)
        return denoised
    except Exception:
        return gray.copy()


def enhance_contrast(gray: np.ndarray) -> np.ndarray:
    """
    Enhance contrast and brightness using Contrast Limited Adaptive Histogram Equalization (CLAHE).
    """
    try:
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        return enhanced
    except Exception:
        return gray.copy()


def apply_adaptive_threshold(gray: np.ndarray) -> np.ndarray:
    """
    Generate clean binarized image using Gaussian adaptive thresholding.
    Ideal for extracting handwritten strokes from paper backgrounds.
    """
    try:
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blockSize=25, C=11
        )
        return binary
    except Exception:
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary


def detect_and_crop_paper(cv_img: np.ndarray) -> Tuple[np.ndarray, bool]:
    """
    Detect document boundaries on camera photograph (e.g. bright prescription paper on dark surface).
    Crops to the paper sheet if a large bright central document is detected.
    """
    try:
        h, w = cv_img.shape[:2]
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img.copy()
        blurred = cv2.GaussianBlur(gray, (9, 9), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Check if corners are dark (background surface) and center is bright (paper)
        corners = [int(thresh[0, 0]), int(thresh[0, w-1]), int(thresh[h-1, 0]), int(thresh[h-1, w-1])]
        if sum(corners) < 255 * 3 and thresh[h//2, w//2] > 0:
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            best_c = None
            max_a = 0
            for c in contours:
                a = cv2.contourArea(c)
                if a > (h * w * 0.35) and a > max_a:
                    max_a = a
                    best_c = c
            if best_c is not None:
                x, y, cw, ch = cv2.boundingRect(best_c)
                pad_x = int(cw * 0.015)
                pad_y = int(ch * 0.015)
                x0 = max(0, x + pad_x)
                y0 = max(0, y + pad_y)
                x1 = min(w, x + cw - pad_x)
                y1 = min(h, y + ch - pad_y)
                if (x1 - x0) > w * 0.45 and (y1 - y0) > h * 0.45:
                    return cv_img[y0:y1, x0:x1], True
    except Exception:
        pass
    return cv_img, False


def crop_document_borders(gray: np.ndarray, margin: int = 10) -> np.ndarray:
    """
    Detect and trim dark scan/photograph borders around the paper document.
    """
    try:
        h, w = gray.shape[:2]
        # Otsu threshold to separate document from background
        _, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(bin_img > 0))
        if len(coords) < 100:
            return gray

        y0, x0 = coords.min(axis=0)
        y1, x1 = coords.max(axis=0)

        # Only crop if substantial non-content border detected
        if (x1 - x0) > w * 0.4 and (y1 - y0) > h * 0.4:
            x0 = max(0, x0 - margin)
            y0 = max(0, y0 - margin)
            x1 = min(w, x1 + margin)
            y1 = min(h, y1 + margin)
            return gray[y0:y1, x0:x1]
        return gray
    except Exception:
        return gray


def analyze_handwriting_features(gray: np.ndarray, binary: np.ndarray) -> Dict[str, Any]:
    """
    Analyze document contours and stroke variances to identify handwritten text characteristics.
    Printed typography has low aspect ratio variance and uniform stroke widths.
    Handwritten doctor text exhibits high variance in slant, line curvature, and stroke thickness.
    """
    try:
        # Invert binary so ink is white
        inv = cv2.bitwise_not(binary)
        contours, _ = cv2.findContours(inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        char_contours = [c for c in contours if 20 < cv2.contourArea(c) < 50000]
        if len(char_contours) < 4:
            return {
                "is_handwritten": False,
                "confidence": 0.5,
                "aspect_var": 0.0,
                "stroke_std": 0.0,
                "score": 0.0,
            }

        aspects = []
        extents = []
        for c in char_contours:
            _, _, cw, ch = cv2.boundingRect(c)
            # Filter out horizontal/vertical divider lines, underlines, and large borders
            if 10 < ch < 180 and 5 < cw < 180 and 0.2 <= (cw / float(ch)) <= 4.0:
                aspects.append(cw / float(ch))
                extents.append(cv2.contourArea(c) / float(cw * ch))

        if len(aspects) < 4:
            return {
                "is_handwritten": False,
                "confidence": 0.5,
                "aspect_var": 0.0,
                "stroke_std": 0.0,
                "score": 0.0,
            }

        aspect_var = float(np.var(aspects))
        extent_var = float(np.var(extents))

        # Measure stroke width variation via distance transform
        dist = cv2.distanceTransform(inv, cv2.DIST_L2, 5)
        stroke_vals = dist[dist > 1.0]
        stroke_std = float(np.std(stroke_vals)) if len(stroke_vals) > 50 else 0.0

        score = (aspect_var * 1.5) + (extent_var * 2.0) + (stroke_std * 0.3)
        is_handwritten = bool(score > 0.42 or aspect_var > 0.30)

        confidence = min(0.98, max(0.40, 0.5 + abs(score - 0.38)))
        return {
            "is_handwritten": is_handwritten,
            "confidence": round(confidence, 3),
            "aspect_var": round(aspect_var, 3),
            "stroke_std": round(stroke_std, 3),
            "score": round(score, 3),
        }
    except Exception:
        return {
            "is_handwritten": False,
            "confidence": 0.5,
            "aspect_var": 0.0,
            "stroke_std": 0.0,
            "score": 0.0,
        }


def detect_tabular_prescription_layout(cv_img: np.ndarray) -> Optional[Dict[str, Any]]:
    """
    Detect whether a document contains a tabular prescription grid with medicine and dosage columns.
    Identifies table boundaries, content rows, column separators, and header areas.
    Returns structured layout metadata if tabular; None if standard unruled/paragraph text.
    """
    try:
        h, w = cv_img.shape[:2]
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img.copy()
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 25, 10)

        # 1. Morphological horizontal line detection (lines spanning >= 20% of width)
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(w * 0.20), 1))
        h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)
        h_proj = np.sum(h_lines > 0, axis=1)

        # Also check colored lines if image is BGR (e.g. green printed grid lines)
        if len(cv_img.shape) == 3 and cv_img.shape[2] == 3:
            b, g, r = cv2.split(cv_img)
            green_diff = (g.astype(int) - r.astype(int) > 6) & (g.astype(int) - b.astype(int) > 6)
            if np.sum(green_diff) > 1000:
                green_lines = cv2.morphologyEx(green_diff.astype(np.uint8) * 255, cv2.MORPH_OPEN, h_kernel)
                h_proj = np.maximum(h_proj, np.sum(green_lines > 0, axis=1))

        peaks = np.where(h_proj > w * 0.18)[0]
        grouped_y = []
        if len(peaks) > 0:
            cur = [peaks[0]]
            for y in peaks[1:]:
                if y <= cur[-1] + 12:
                    cur.append(y)
                else:
                    grouped_y.append(int(np.mean(cur)))
                    cur = [y]
            grouped_y.append(int(np.mean(cur)))

        # Find runs of consecutive rows with regular spacing
        if len(grouped_y) < 4:
            return None

        diffs = [grouped_y[i + 1] - grouped_y[i] for i in range(len(grouped_y) - 1)]
        best_run = []
        current_run = []
        for i, d in enumerate(diffs):
            if 50 <= d <= 220:
                if not current_run:
                    current_run = [i]
                else:
                    prev_d = diffs[current_run[-1]]
                    if abs(d - prev_d) <= max(30, prev_d * 0.45):
                        current_run.append(i)
                    else:
                        if len(current_run) > len(best_run):
                            best_run = current_run
                        current_run = [i]
            else:
                if len(current_run) > len(best_run):
                    best_run = current_run
                current_run = []
        if len(current_run) > len(best_run):
            best_run = current_run

        if len(best_run) < 4:
            return None

        start_line_idx = best_run[0]
        end_line_idx = best_run[-1] + 1
        table_y = grouped_y[start_line_idx : end_line_idx + 1]

        # A prescription grid table must contain at least 5 row lines (4+ cells)
        # and span a significant portion (>= 30%) of the document height
        if len(table_y) < 5 or (table_y[-1] - table_y[0]) < h * 0.30:
            return None

        # Identify rows with handwriting ink content
        content_rows = []
        for i in range(len(table_y) - 1):
            y1, y2 = table_y[i], table_y[i + 1]
            roi = cv_img[y1 + 8 : y2 - 8, int(w * 0.05) : int(w * 0.95)]
            if len(roi.shape) == 3:
                b_roi, g_roi, r_roi = cv2.split(roi)
                ink = (b_roi < 140) & (r_roi < 140) & (g_roi < 140)
                green = (g_roi.astype(int) - r_roi.astype(int) > 6) & (g_roi.astype(int) - b_roi.astype(int) > 6)
                ink = ink & ~green
            else:
                ink = roi < 120

            ink_count = int(np.sum(ink))
            if ink_count > 1000:
                content_rows.append((y1, y2, ink_count))

        # Detect vertical column separator between medicine name and schedule columns (around 60%..80% width)
        col_split_x = int(w * 0.68)
        table_top = table_y[0]
        table_bot = table_y[-1]
        v_roi = thresh[table_top:table_bot, int(w * 0.55) : int(w * 0.85)]
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, int((table_bot - table_top) * 0.15)))
        v_lines = cv2.morphologyEx(v_roi, cv2.MORPH_OPEN, v_kernel)
        v_proj = np.sum(v_lines > 0, axis=0)
        v_peaks = np.where(v_proj > (table_bot - table_top) * 0.22)[0]
        if len(v_peaks) > 0:
            col_split_x = int(w * 0.55) + int(np.mean(v_peaks))

        return {
            "is_tabular": True,
            "table_y": table_y,
            "content_rows": content_rows,
            "col_split_x": col_split_x,
            "header_y": (0, table_top),
            "table_top": table_top,
            "table_bot": table_bot,
        }
    except Exception:
        return None


def preprocess_prescription_image(
    image_or_path: Union[Image.Image, np.ndarray, str, Path],
    target_dpi: int = 300
) -> Dict[str, Any]:
    """
    Comprehensive document preprocessing pipeline.
    Preserves the original image while generating enhanced grayscale, deskewed,
    and adaptively thresholded representations for handwriting and printed OCR.

    Returns:
        {
            "original_pil": Image.Image (pristine original untouched),
            "enhanced_pil": Image.Image (shadow-flattened, contrast-boosted),
            "binary_pil": Image.Image (adaptively thresholded binarization),
            "deskew_angle": float,
            "rotation_applied": int,
            "is_handwritten": bool,
            "handwriting_metrics": dict
        }
    """
    # 1. Load original image
    if isinstance(image_or_path, (str, Path)):
        original_pil = Image.open(str(image_or_path))
    elif isinstance(image_or_path, np.ndarray):
        original_pil = cv_to_pil(image_or_path)
    else:
        original_pil = image_or_path

    # Keep pristine copy
    pristine_copy = original_pil.copy()

    # 2. Correct EXIF orientation
    working_pil = correct_exif_orientation(original_pil)

    # 3. Upscale if image resolution is low (< 1400px on max dimension)
    w, h = working_pil.size
    if max(w, h) < 1400:
        scale = max(1.5, 1600.0 / max(w, h))
        new_size = (int(w * scale), int(h * scale))
        working_pil = working_pil.resize(new_size, Image.Resampling.BICUBIC)

    # 4. Correct 90/180/270 rotation via OSD
    working_pil, rotation_applied = detect_and_correct_rotation(working_pil)

    # 5. Crop document boundaries (table/desk background and scanner borders)
    cv_working = pil_to_cv(working_pil)
    cv_working, _ = detect_and_crop_paper(cv_working)
    working_pil = cv_to_pil(cv_working)

    # 6. Extract ink-contrast channel (Red channel / min(R, G)) for blue & dark pen ink
    ink_pil = None
    if len(cv_working.shape) == 3 and cv_working.shape[2] == 3:
        b, g, r = cv2.split(cv_working)
        ink_channel = np.minimum(r, g)
        _, ink_bin = cv2.threshold(ink_channel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        ink_pil = cv_to_pil(ink_bin)

    # 7. Convert to OpenCV grayscale
    gray = to_grayscale(working_pil)
    gray = crop_document_borders(gray)

    # 8. Deskew minor angles
    deskewed_gray, deskew_angle = correct_skew(gray)

    # 9. Remove shadows, background gradients, and noise
    flattened_gray = remove_shadows_and_noise(deskewed_gray)

    # 10. Enhance contrast via CLAHE
    enhanced_gray = enhance_contrast(flattened_gray)

    # 11. Adaptive thresholding
    binary = apply_adaptive_threshold(enhanced_gray)

    # 12. Handwriting feature analysis
    hw_metrics = analyze_handwriting_features(enhanced_gray, binary)

    return {
        "original_pil": pristine_copy,
        "enhanced_pil": cv_to_pil(enhanced_gray),
        "binary_pil": cv_to_pil(binary),
        "ink_pil": ink_pil,
        "deskew_angle": deskew_angle,
        "rotation_applied": rotation_applied,
        "is_handwritten": hw_metrics["is_handwritten"],
        "handwriting_metrics": hw_metrics,
    }


def crop_paper_sheet_with_bbox(cv_img: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int, int, int], bool]:
    """
    Detect and crop a bright paper prescription photographed on a dark/cluttered surface
    (e.g. desk, cloth, calculator) while preserving exact coordinates in the original image.

    Returns:
        (cropped_bgr, (x0, y0, width, height), was_cropped)
    """
    h0, w0 = cv_img.shape[:2]
    try:
        gray0 = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img.copy()
        blurred = cv2.GaussianBlur(gray0, (15, 15), 0)
        _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        corners = [int(otsu[0, 0]), int(otsu[0, w0 - 1]), int(otsu[h0 - 1, 0]), int(otsu[h0 - 1, w0 - 1])]
        # Already a clean full-bleed scan or digital image when at least 3 corners are bright paper
        if sum(corners) >= 255 * 3:
            return cv_img, (0, 0, w0, h0), False

        if len(cv_img.shape) == 3 and cv_img.shape[2] == 3:
            hsv0 = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
            is_paper = (otsu > 0) & (hsv0[:, :, 1] < 92)
        else:
            is_paper = otsu > 0

        # Row-wise and column-wise paper coverage trims cluttered top/bottom/side backgrounds cleanly
        row_frac = np.mean(is_paper, axis=1)
        col_frac = np.mean(is_paper, axis=0)
        good_rows = np.where(row_frac > 0.70)[0]
        good_cols = np.where(col_frac > 0.70)[0]

        if len(good_rows) >= int(h0 * 0.45) and len(good_cols) >= int(w0 * 0.45):
            y0_p, y1_p = int(good_rows[0]), int(good_rows[-1]) + 1
            x0_p, x1_p = int(good_cols[0]), int(good_cols[-1]) + 1
        else:
            paper_mask = is_paper.astype(np.uint8) * 255
            paper_mask = cv2.morphologyEx(paper_mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (41, 41)))
            paper_mask = cv2.morphologyEx(paper_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (31, 31)))
            cnts, _ = cv2.findContours(paper_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                return cv_img, (0, 0, w0, h0), False
            best = max(cnts, key=cv2.contourArea)
            if cv2.contourArea(best) < h0 * w0 * 0.30:
                return cv_img, (0, 0, w0, h0), False
            bx, by, bw, bh = cv2.boundingRect(best)
            x0_p, y0_p, x1_p, y1_p = bx, by, bx + bw, by + bh

        cw = x1_p - x0_p
        ch = y1_p - y0_p
        if cw > int(w0 * 0.45) and ch > int(h0 * 0.45):
            # Mild inset eliminates paper-edge shadow strips and staples
            ix = int(cw * 0.02)
            iy = int(ch * 0.015)
            x0 = max(0, x0_p + ix)
            y0 = max(0, y0_p + iy)
            x1 = min(w0, x1_p - ix)
            y1 = min(h0, y1_p - iy)
            if (x1 - x0) > int(w0 * 0.40) and (y1 - y0) > int(h0 * 0.40):
                return cv_img[y0:y1, x0:x1], (x0, y0, x1 - x0, y1 - y0), True
    except Exception:
        pass
    return cv_img, (0, 0, w0, h0), False


def render_shadow_free_ink(cv_img: np.ndarray) -> Dict[str, Any]:
    """
    Illumination-normalized ink renderer for photographed and scanned documents.
    Removes uneven lighting and paper shadows via morphological background division,
    preserves anti-aliased blue/black pen strokes for LSTM OCR, and builds a clean binary ink mask.
    """
    h, w = cv_img.shape[:2]
    k_sz = max(25, min(51, (min(h, w) // 28) | 1))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_sz, k_sz))

    if len(cv_img.shape) == 3 and cv_img.shape[2] == 3:
        b, g, r = cv2.split(cv_img)
        nb = np.clip((b.astype(np.float32) / np.maximum(cv2.morphologyEx(b, cv2.MORPH_CLOSE, kernel).astype(np.float32), 1.0)) * 255.0, 0, 255).astype(np.uint8)
        ng = np.clip((g.astype(np.float32) / np.maximum(cv2.morphologyEx(g, cv2.MORPH_CLOSE, kernel).astype(np.float32), 1.0)) * 255.0, 0, 255).astype(np.uint8)
        nr = np.clip((r.astype(np.float32) / np.maximum(cv2.morphologyEx(r, cv2.MORPH_CLOSE, kernel).astype(np.float32), 1.0)) * 255.0, 0, 255).astype(np.uint8)
        ink_gray = np.minimum(nr, ng)
        blue_ink = ((nb.astype(np.int16) - nr.astype(np.int16)) > 14) & (ink_gray < 218)
        dark_ink = ink_gray < 185
        all_ink = blue_ink | dark_ink
        blue_ratio = float(np.sum(blue_ink)) / max(1.0, float(np.sum(all_ink)))
    else:
        gray = cv_img.copy()
        bg = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
        ink_gray = np.clip((gray.astype(np.float32) / np.maximum(bg.astype(np.float32), 1.0)) * 255.0, 0, 255).astype(np.uint8)
        all_ink = ink_gray < 185
        blue_ratio = 0.0

    # Smooth contrast stretch keeps handwriting stroke edges intact for Tesseract LSTM
    soft_gray = np.clip((ink_gray.astype(np.float32) - 85.0) * (255.0 / (238.0 - 85.0)), 0, 255).astype(np.uint8)

    ink_mask = all_ink.astype(np.uint8) * 255
    ink_mask = cv2.morphologyEx(ink_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
    # Zero out outer 1% vertical margins so faint paper edges cannot bridge rows
    mx = max(4, int(w * 0.01))
    ink_mask[:, :mx] = 0
    ink_mask[:, max(0, w - mx):] = 0

    return {
        "soft_gray": soft_gray,
        "ink_gray": ink_gray,
        "ink_mask": ink_mask,
        "blue_ink_ratio": round(blue_ratio, 3),
    }


def detect_horizontal_dividers(mask: np.ndarray, min_width_frac: float = 0.38) -> List[int]:
    """Detect horizontal rule or handwritten divider lines spanning at least min_width_frac of width."""
    mh, mw = mask.shape[:2]
    if mw < 40 or mh < 20:
        return []
    k_w = max(30, int(mw * min_width_frac))
    h_rules = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, 1)))
    rule_ys = np.where(np.sum(h_rules > 0, axis=1) > mw * max(0.32, min_width_frac - 0.04))[0]
    if len(rule_ys) == 0:
        return []
    grouped = []
    cur = [int(rule_ys[0])]
    for y in rule_ys[1:]:
        yi = int(y)
        if yi <= cur[-1] + 10:
            cur.append(yi)
        else:
            grouped.append(int(np.mean(cur)))
            cur = [yi]
    grouped.append(int(np.mean(cur)))
    return grouped


def detect_two_column_split(ink_mask: np.ndarray, y_start: int, y_end: int) -> Optional[int]:
    """
    Detect whether the prescription body between y_start and y_end has a two-column layout
    (e.g., left clinical observations/vitals column + right prescription column).
    Returns the split x-coordinate if a clear vertical whitespace valley exists, else None.
    """
    h, w = ink_mask.shape[:2]
    y0 = max(0, min(y_start, h - 1))
    y1 = max(y0 + 1, min(y_end, h))
    body = ink_mask[y0:y1, :]
    bh, bw = body.shape[:2]
    if bh < 100 or bw < 200:
        return None

    v_proj = np.sum(body > 0, axis=0)
    kw = max(5, bw // 40)
    v_smooth = np.convolve(v_proj, np.ones(kw) / kw, mode="same")

    x_min, x_max = int(bw * 0.20), int(bw * 0.54)
    if x_max <= x_min:
        return None

    sub = v_smooth[x_min:x_max]
    vi = int(np.argmin(sub))
    vx = x_min + vi
    valley_val = float(sub[vi])

    left_mass = float(np.sum(v_proj[:vx]))
    right_mass = float(np.sum(v_proj[vx:]))
    max_side = max(
        float(np.max(v_smooth[:vx])) if vx > 0 else 0.0,
        float(np.max(v_smooth[vx:])) if vx < bw else 0.0,
    )

    if max_side <= 0:
        return None

    # Require near-empty vertical valley, meaningful ink on both sides, and minimal crossing lines
    cross_strip = body[:, max(0, vx - 8):min(bw, vx + 8)]
    cross_rows = int(np.sum(np.sum(cross_strip > 0, axis=1) > 0))
    if (
        valley_val < max_side * 0.10
        and left_mass > (bw * bh * 0.0025)
        and right_mass > (bw * bh * 0.0045)
        and cross_rows < int(bh * 0.07)
    ):
        return int(vx)
    return None


def segment_zone_lines(mask: np.ndarray, ox: int = 0, oy: int = 0) -> Tuple[List[Dict[str, Any]], List[int]]:
    """
    Segment a document region into ordered horizontal text lines using connected components
    and vertical-overlap clustering (immune to vertical border bridges and horizontal dividers).

    Returns:
        (lines_list, abs_divider_ys)
    """
    mh, mw = mask.shape[:2]
    if mh < 12 or mw < 20:
        return [], []

    div_ys = detect_horizontal_dividers(mask, min_width_frac=0.38)
    clean_m = mask.copy()
    for dy in div_ys:
        clean_m[max(0, dy - 6):min(mh, dy + 7), :] = 0

    dil_w = max(12, min(42, int(mw * 0.05)))
    dil = cv2.dilate(clean_m, cv2.getStructuringElement(cv2.MORPH_RECT, (dil_w, 2)))
    n_lbl, _, stats, _ = cv2.connectedComponentsWithStats(dil)

    boxes = []
    for i in range(1, n_lbl):
        x, y, bw, bh, area = [int(v) for v in stats[i]]
        if area < 70 or bw < 12 or bh < 10:
            continue
        # Reject tall thin border/crease lines
        if bh > int(mh * 0.45) and bw < int(mw * 0.14):
            continue
        # Reject thin horizontal underlines missed by divider filter
        if bw > int(mw * 0.35) and bh <= 14 and (area / max(1, bw * bh)) > 0.35:
            div_ys.append(y + bh // 2)
            continue
        boxes.append([x, y, x + bw, y + bh, area])

    boxes.sort(key=lambda b: (b[1], b[0]))

    # Merge boxes with >= 40% vertical overlap into a single logical text line
    lines: List[Dict[str, Any]] = []
    for bx0, by0, bx1, by1, area in boxes:
        merged = False
        for ln in lines:
            ov = min(by1, ln["y1"]) - max(by0, ln["y0"])
            min_h = min(by1 - by0, ln["y1"] - ln["y0"])
            if ov > 0 and ov >= 0.40 * max(1, min_h):
                ln["x0"] = min(ln["x0"], bx0)
                ln["y0"] = min(ln["y0"], by0)
                ln["x1"] = max(ln["x1"], bx1)
                ln["y1"] = max(ln["y1"], by1)
                ln["area"] += area
                ln["components"].append([bx0, by0, bx1, by1])
                merged = True
                break
        if not merged:
            lines.append({
                "x0": bx0, "y0": by0, "x1": bx1, "y1": by1,
                "area": area,
                "components": [[bx0, by0, bx1, by1]],
            })

    lines.sort(key=lambda l: l["y0"])
    for ln in lines:
        ln["abs_x0"] = ox + ln["x0"]
        ln["abs_y0"] = oy + ln["y0"]
        ln["abs_x1"] = ox + ln["x1"]
        ln["abs_y1"] = oy + ln["y1"]
        ln["width"] = ln["x1"] - ln["x0"]
        ln["height"] = ln["y1"] - ln["y0"]

    abs_div_ys = sorted(set(oy + d for d in div_ys))
    return lines, abs_div_ys


def detect_freeform_prescription_layout(
    image_or_path: Union[Image.Image, np.ndarray, str, Path]
) -> Optional[Dict[str, Any]]:
    """
    Generalized document-region detector for free-form handwritten prescriptions
    (two-column clinic pads, single-column handwritten lists, paragraph notes, mixed print + ink).

    Maps every detected zone and line back to normalized [x, y, w, h] coordinates (0..1)
    on the pristine original (EXIF-corrected) image for doctor verification.
    """
    try:
        if isinstance(image_or_path, (str, Path)):
            pil_img = correct_exif_orientation(Image.open(str(image_or_path)))
            cv_raw = pil_to_cv(pil_img)
        elif isinstance(image_or_path, Image.Image):
            pil_img = correct_exif_orientation(image_or_path)
            cv_raw = pil_to_cv(pil_img)
        else:
            cv_raw = image_or_path

        if cv_raw is None or cv_raw.size == 0:
            return None

        orig_h, orig_w = cv_raw.shape[:2]
        cropped_bgr, (cx0, cy0, cw0, ch0), was_cropped = crop_paper_sheet_with_bbox(cv_raw)

        # Normalize working resolution to ~1800px max dimension for consistent handwriting features
        ch, cw = cropped_bgr.shape[:2]
        scale = 1.0
        if max(ch, cw) < 1600:
            scale = 1800.0 / float(max(ch, cw))
            work_bgr = cv2.resize(cropped_bgr, (int(cw * scale), int(ch * scale)), interpolation=cv2.INTER_CUBIC)
        elif max(ch, cw) > 2400:
            scale = 2000.0 / float(max(ch, cw))
            work_bgr = cv2.resize(cropped_bgr, (int(cw * scale), int(ch * scale)), interpolation=cv2.INTER_AREA)
        else:
            work_bgr = cropped_bgr

        wh, ww = work_bgr.shape[:2]
        ink_data = render_shadow_free_ink(work_bgr)
        soft_gray = ink_data["soft_gray"]
        ink_mask = ink_data["ink_mask"]
        blue_ratio = ink_data["blue_ink_ratio"]

        def to_orig_norm_bbox(x0: int, y0: int, x1: int, y1: int) -> List[float]:
            ox0 = cx0 + (x0 / scale)
            oy0 = cy0 + (y0 / scale)
            ox1 = cx0 + (x1 / scale)
            oy1 = cy0 + (y1 / scale)
            nx = max(0.0, min(1.0, ox0 / float(orig_w)))
            ny = max(0.0, min(1.0, oy0 / float(orig_h)))
            nw = max(0.0, min(1.0 - nx, (ox1 - ox0) / float(orig_w)))
            nh = max(0.0, min(1.0 - ny, (oy1 - oy0) / float(orig_h)))
            return [round(nx, 4), round(ny, 4), round(nw, 4), round(nh, 4)]

        # 1. Footer boundary: look for horizontal divider line in bottom 24%
        bot_start = int(wh * 0.76)
        bot_divs = detect_horizontal_dividers(ink_mask[bot_start:, :], min_width_frac=0.45)
        footer_y = (bot_start + bot_divs[0]) if bot_divs else int(wh * 0.92)

        # 2. Check for two-column split starting around y = 28%..34% down to footer_y
        valley_x = None
        split_start_y = int(wh * 0.28)
        for frac in (0.28, 0.32, 0.36):
            cand_y = int(wh * frac)
            vx = detect_two_column_split(ink_mask, cand_y, footer_y)
            if vx is not None:
                valley_x = vx
                split_start_y = cand_y
                break

        # Refine split_start_y upward to see if columns start even higher (e.g. y=22%)
        # or if there is a wide top clinical notes band spanning across valley_x!
        if valley_x is not None:
            # Find lowest row above split_start_y (down to y=18%) that has ink crossing near valley_x
            # OR spans wide across both sides (header/date/symptoms band)
            top_scan_start = int(wh * 0.16)
            cross_band = ink_mask[top_scan_start:split_start_y, max(0, valley_x - 25):min(ww, valley_x + 25)]
            cross_rows = np.where(np.sum(cross_band > 0, axis=1) > 0)[0]
            if len(cross_rows) > 0:
                last_cross_y = top_scan_start + int(cross_rows[-1]) + 8
                # Start two columns just below the last full-width band
                split_start_y = min(footer_y - 100, max(int(wh * 0.22), last_cross_y))
            else:
                # Check if columns actually begin cleanly at y=22%
                vx_high = detect_two_column_split(ink_mask, int(wh * 0.22), footer_y)
                if vx_high is not None:
                    split_start_y = int(wh * 0.22)

        return {
            "work_bgr": work_bgr,
            "soft_gray": soft_gray,
            "ink_mask": ink_mask,
            "blue_ink_ratio": blue_ratio,
            "was_cropped": was_cropped,
            "orig_size": (orig_w, orig_h),
            "work_size": (ww, wh),
            "crop_bbox": (cx0, cy0, cw0, ch0),
            "scale": scale,
            "footer_y": footer_y,
            "valley_x": valley_x,
            "is_two_column": valley_x is not None,
            "split_start_y": split_start_y,
            "to_orig_norm_bbox": to_orig_norm_bbox,
        }
    except Exception:
        return None
