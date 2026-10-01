import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
from PIL import Image
import pytesseract

from app.core.config import settings

logger = logging.getLogger("evalai.ocr")


class OCRError(Exception):
    """Raised when an error occurs during OCR processing."""
    pass


def extract_ocr_data(
    image: Union[np.ndarray, Image.Image, str, Path],
    lang: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run Tesseract OCR on an image and return structured OCR output:
    - text: full page text
    - confidence: mean confidence score (0.0 to 100.0) derived from word-level Tesseract data
    - word_boxes: list of dicts with word, conf, left, top, width, height, line_num, block_num
    - raw_data: pytesseract Output.DICT dictionary
    - success: bool
    - error: Optional[str]
    """
    ocr_lang = lang or settings.OCR_LANGUAGE or "eng"
    
    # Prepare image for pytesseract
    if isinstance(image, (str, Path)):
        img_input = Image.open(str(image))
    elif isinstance(image, np.ndarray):
        if len(image.shape) == 2:
            img_input = Image.fromarray(image)
        else:
            img_input = Image.fromarray(image[:, :, ::-1])  # BGR to RGB
    elif isinstance(image, Image.Image):
        img_input = image
    else:
        raise OCRError(f"Unsupported image input type: {type(image)}")

    try:
        # Run image_to_data to obtain bounding boxes and word-level confidences
        data = pytesseract.image_to_data(
            img_input,
            lang=ocr_lang,
            output_type=pytesseract.Output.DICT,
        )

        n_boxes = len(data["text"])
        valid_confs: List[float] = []
        word_boxes: List[Dict[str, Any]] = []

        for i in range(n_boxes):
            word = str(data["text"][i]).strip()
            conf_val = float(data["conf"][i])

            # Tesseract uses -1 for layout blocks without text
            if conf_val >= 0:
                box_info = {
                    "text": word,
                    "conf": conf_val,
                    "left": int(data["left"][i]),
                    "top": int(data["top"][i]),
                    "width": int(data["width"][i]),
                    "height": int(data["height"][i]),
                    "line_num": int(data["line_num"][i]),
                    "block_num": int(data["block_num"][i]),
                    "par_num": int(data["par_num"][i]),
                }
                word_boxes.append(box_info)
                if word:  # only include non-empty words in confidence calculation
                    valid_confs.append(conf_val)

        # Calculate overall page confidence from real word confidences
        page_conf: Optional[float] = None
        if valid_confs:
            page_conf = round(float(np.mean(valid_confs)), 2)

        # Get full text string
        full_text = pytesseract.image_to_string(img_input, lang=ocr_lang).strip()

        return {
            "text": full_text,
            "confidence": page_conf,
            "word_boxes": word_boxes,
            "raw_data": data,
            "success": True,
            "error": None,
        }

    except pytesseract.TesseractNotFoundError as e:
        logger.error(f"Tesseract OCR executable not found: {e}")
        return {
            "text": "",
            "confidence": None,
            "word_boxes": [],
            "raw_data": {},
            "success": False,
            "error": "Tesseract OCR is not installed or not found in system PATH",
        }
    except Exception as e:
        logger.error(f"Tesseract OCR processing failed: {e}")
        return {
            "text": "",
            "confidence": None,
            "word_boxes": [],
            "raw_data": {},
            "success": False,
            "error": str(e),
        }


def extract_text_from_region(
    image: Union[np.ndarray, Image.Image],
    lang: Optional[str] = None,
) -> Dict[str, Any]:
    """Run OCR on a cropped region."""
    return extract_ocr_data(image, lang=lang)
