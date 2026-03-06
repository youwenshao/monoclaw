"""VisaDoc OCR — document scanning, parsing, and validation for HK immigration."""

from immigration.visa_doc_ocr.ocr.vision_engine import process_image
from immigration.visa_doc_ocr.ocr.tesseract_engine import process_image_tesseract
from immigration.visa_doc_ocr.ocr.preprocessor import preprocess_image
from immigration.visa_doc_ocr.ocr.confidence import score_fields

__all__ = [
    "process_image",
    "process_image_tesseract",
    "preprocess_image",
    "score_fields",
]
