import io
import math
from pathlib import Path
from typing import Optional, Tuple
import cv2
import numpy as np
from PIL import Image


class ImageProcessingError(Exception):
    """Raised when an error occurs during image preprocessing."""
    pass


def load_image_from_bytes(image_bytes: bytes) -> np.ndarray:
    """Load image from byte array into an OpenCV BGR numpy array."""
    try:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            # Fallback to Pillow
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return img
    except Exception as e:
        raise ImageProcessingError(f"Failed to decode image: {str(e)}") from e


def load_image_from_path(image_path: str) -> np.ndarray:
    """Load image from file path into an OpenCV BGR numpy array."""
    path = Path(image_path)
    if not path.exists():
        raise ImageProcessingError(f"Image file not found at '{image_path}'")
    try:
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            pil_img = Image.open(str(path)).convert("RGB")
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return img
    except Exception as e:
        raise ImageProcessingError(f"Failed to read image from '{image_path}': {str(e)}") from e


def save_image(img: np.ndarray, output_path: str) -> str:
    """Save an OpenCV numpy array image to disk."""
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    success = cv2.imwrite(str(out_p), img)
    if not success:
        # Fallback to Pillow
        if len(img.shape) == 2:
            pil_img = Image.fromarray(img)
        else:
            pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        pil_img.save(str(out_p))
    return str(out_p.resolve())


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """Convert BGR image to grayscale if not already grayscale."""
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def enhance_contrast(gray: np.ndarray, clip_limit: float = 2.0, tile_grid_size: Tuple[int, int] = (8, 8)) -> np.ndarray:
    """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to enhance text contrast."""
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return clahe.apply(gray)


def denoise_image(gray: np.ndarray) -> np.ndarray:
    """Apply bilateral filtering or Gaussian blur to preserve edges while removing background paper noise."""
    return cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)


def estimate_skew_angle(gray: np.ndarray) -> float:
    """
    Estimate skew angle in degrees using Otsu binarization and minimum area rectangle.
    Returns angle between -45.0 and 45.0 degrees.
    """
    try:
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 50:
            return 0.0

        rect = cv2.minAreaRect(coords)
        angle = rect[-1]

        # Normalize angle to [-45, 45]
        if angle < -45:
            angle = -(90 + angle)
        elif angle > 45:
            angle = 90 - angle
        else:
            angle = -angle

        # If angle is negligible (< 0.5 degrees), do not rotate
        if abs(angle) < 0.5 or abs(angle) > 45.0:
            return 0.0

        return angle
    except Exception:
        return 0.0


def rotate_image(img: np.ndarray, angle: float) -> np.ndarray:
    """Rotate image by given angle in degrees around its center with white border padding."""
    if abs(angle) < 0.1:
        return img

    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    rot_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # Calculate new bounding dimensions
    cos = np.abs(rot_matrix[0, 0])
    sin = np.abs(rot_matrix[0, 1])
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))

    # Adjust transformation matrix
    rot_matrix[0, 2] += (new_w / 2) - center[0]
    rot_matrix[1, 2] += (new_h / 2) - center[1]

    border_val = 255 if len(img.shape) == 2 else (255, 255, 255)
    return cv2.warpAffine(
        img,
        rot_matrix,
        (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_val,
    )


def binarize_adaptive(gray: np.ndarray) -> np.ndarray:
    """Apply adaptive Gaussian thresholding suitable for uneven lighting on paper."""
    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=21,
        C=10,
    )


def preprocess_page(
    img: np.ndarray,
    deskew: bool = True,
    enhance: bool = True,
    denoise: bool = True,
) -> np.ndarray:
    """
    Standard preprocessing pipeline for scanned/photographed handwritten answer sheet pages.
    Preserves grayscale clarity for OCR while removing skew, low contrast, and lighting artifacts.
    """
    gray = to_grayscale(img)

    if deskew:
        angle = estimate_skew_angle(gray)
        if abs(angle) >= 0.5:
            gray = rotate_image(gray, angle)

    if denoise:
        gray = denoise_image(gray)

    if enhance:
        gray = enhance_contrast(gray)

    return gray


def crop_image_region(
    img: np.ndarray,
    top: int,
    bottom: int,
    left: Optional[int] = None,
    right: Optional[int] = None,
    padding_y: int = 15,
    padding_x: int = 10,
) -> np.ndarray:
    """
    Crop a vertical/horizontal slice of an image with bounds checking and optional padding.
    """
    h, w = img.shape[:2]

    # Apply padding
    y_min = max(0, int(top) - padding_y)
    y_max = min(h, int(bottom) + padding_y)

    x_min = max(0, int(left) - padding_x) if left is not None else 0
    x_max = min(w, int(right) + padding_x) if right is not None else w

    if y_max <= y_min or x_max <= x_min:
        # Fallback to minimal valid region
        y_min = 0
        y_max = max(1, h)
        x_min = 0
        x_max = max(1, w)

    return img[y_min:y_max, x_min:x_max]
