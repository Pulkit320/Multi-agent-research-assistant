import os
import logging
import pdfplumber

# Set up logger
logger = logging.getLogger(__name__)

# Make OCR dependencies optional for robustness
try:
    from pdf2image import convert_from_path
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    logger.warning("OCR dependencies (pdf2image or pytesseract) not installed. OCR fallbacks are disabled.")

def ocr_fallback(pdf_path: str, page_number: int) -> str:
    """
    Attempts to OCR a page image if digital text extraction yielded nothing.
    
    Returns:
        The extracted OCR text or an empty string if dependencies are missing or it failed.
    """
    if not HAS_OCR:
        return ""
    try:
        pages = convert_from_path(pdf_path, first_page=page_number, last_page=page_number)
        if pages:
            ocr_text = pytesseract.image_to_string(pages[0])
            return ocr_text.strip()
    except Exception as e:
        logger.error(f"OCR fallback failed for {pdf_path} page {page_number}: {e}")
    return ""

def extract_text(pdf_path: str) -> list[dict]:
    """
    Extracts text from a PDF file page-by-page.
    
    This function exists to isolate raw document text and preserve page numbers
    for citations.
    
    Args:
        pdf_path: Path to the PDF file.
        
    Returns:
        A list of page dictionaries containing 'page_number', 'text', 'is_empty_or_scanned'.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The PDF file at '{pdf_path}' was not found.")

    extracted_pages = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_num = page.page_number
                raw_text = page.extract_text()
                
                clean_text = raw_text.strip() if raw_text else ""
                
                is_empty_or_scanned = len(clean_text) == 0
                if is_empty_or_scanned:
                    ocr_text = ocr_fallback(pdf_path, page_num)
                    if ocr_text:
                        clean_text = ocr_text
                        is_empty_or_scanned = False
                        
                extracted_pages.append({
                    "page_number": page_num,
                    "text": clean_text,
                    "is_empty_or_scanned": is_empty_or_scanned
                })
                
    except Exception as e:
        raise ValueError(f"Failed to parse PDF file '{pdf_path}'. Details: {e}")

    return extracted_pages
