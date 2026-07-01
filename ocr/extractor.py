import cv2
import numpy as np
import pytesseract
import os
from PIL import Image
from typing import Tuple, Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger("extractor")

def deskew_image(image: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Attempts to detect text orientation and rotate/deskew the image using Tesseract OSD (Orientation and Script Detection).
    Returns (corrected_image, rotation_angle).
    """
    try:
        # Tesseract OSD requires a minimum amount of text
        osd = pytesseract.image_to_osd(image)
        logger.info(f"OSD Raw data: {osd.replace(chr(10), ' | ')}")
        
        # Parse rotation
        rotation_match = [line for line in osd.split('\n') if "Rotate:" in line]
        if rotation_match:
            angle = float(rotation_match[0].split(':')[-1].strip())
            if angle != 0:
                logger.info(f"Rotating image by {angle} degrees.")
                # OpenCV rotation
                if angle == 90:
                    rotated = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
                elif angle == 180:
                    rotated = cv2.rotate(image, cv2.ROTATE_180)
                elif angle == 270:
                    rotated = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
                else:
                    # Arbitrary rotation
                    (h, w) = image.shape[:2]
                    center = (w // 2, h // 2)
                    matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
                    rotated = cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                return rotated, angle
    except Exception as e:
        logger.warning(f"OSD / deskewing failed (this is expected for short/rotated text or if OSD data is missing): {e}")
        
    return image, 0.0

def preprocess_image_pipeline(image_path: str, output_debug_path: Optional[str] = None) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Reads an image and runs it through the preprocessing pipeline:
    1. Resize (upscale if small)
    2. Rotation correction
    3. Grayscale
    4. Contrast enhancement (CLAHE)
    5. Noise removal (Bilateral filter)
    6. Adaptive Thresholding
    Returns (original_image, preprocessed_image, rotation_angle).
    """
    logger.info(f"Preprocessing image: {image_path}")
    
    # Read image using OpenCV (use unicode-safe reading because paths might have spaces/unicode)
    # cv2.imread doesn't handle unicode paths well on Windows, so we read using numpy
    try:
        img_array = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.error(f"Failed to read image using OpenCV: {e}")
        # Fallback to PIL
        pil_img = Image.open(image_path).convert('RGB')
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    if img is None:
        raise ValueError(f"Could not load image at {image_path}")
        
    original = img.copy()
    h, w = img.shape[:2]
    
    # Step 1: Upscale if resolution is too low (< 1500px in either dimension)
    # Small text on business cards benefits enormously from upscaling before OCR
    min_dim = min(h, w)
    if min_dim < 1000:
        factor = 2
        logger.info(f"Image dimension ({min_dim}px) is small. Upscaling by {factor}x.")
        img = cv2.resize(img, (w * factor, h * factor), interpolation=cv2.INTER_CUBIC)
        h, w = img.shape[:2]
        
    # Step 2: Rotation / Deskewing
    img, angle = deskew_image(img)
    
    # Step 3: Convert to Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Step 4: Contrast Enhancement (CLAHE - Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Step 5: Noise Removal (Bilateral Filter preserves edges while blurring grain)
    denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
    
    # Step 6: Binarization (Adaptive Thresholding is robust to shadow and lighting variations)
    # OCR works best with clear black text on white background
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    
    # Save debug preprocessed image if path specified
    if output_debug_path:
        try:
            cv2.imwrite(output_debug_path, thresh)
            logger.info(f"Saved debug preprocessed image to: {output_debug_path}")
        except Exception as e:
            logger.warning(f"Failed to save debug preprocessed image: {e}")
            
    return original, thresh, angle

def clean_ocr_text(raw_text: str) -> str:
    """
    Cleans raw OCR output by:
    - Normalizing spaces and tabs
    - Restoring broken lines
    - Stripping empty lines/junk characters
    """
    if not raw_text:
        return ""
        
    # Split text into lines
    lines = raw_text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Remove extra spaces
        line = re_sub_spaces(line)
        line = line.strip()
        if line:
            # Skip very short junk lines (e.g. single symbols or artifacts)
            if len(line) == 1 and not line.isalnum():
                continue
            cleaned_lines.append(line)
            
    # Join with newlines
    text = '\n'.join(cleaned_lines)
    return text

def re_sub_spaces(text: str) -> str:
    # Substitute multiple whitespace with a single space
    import re
    return re.sub(r'\s+', ' ', text)

def extract_text_and_confidence(preprocessed_img: np.ndarray) -> Tuple[str, float]:
    """
    Extracts text and average word confidence from a preprocessed image.
    Returns (cleaned_text, average_confidence_0_to_100).
    """
    logger.info("Starting Tesseract OCR extraction.")
    
    # Convert OpenCV image to PIL Image for Tesseract
    pil_img = Image.fromarray(preprocessed_img)
    
    # Extract raw text
    # Page segmentation mode (PSM) 11: Sparse text. Find as much text as possible in no particular order.
    # PSM 3: Fully automatic page segmentation, but no OSD. (default)
    # For business cards, PSM 3 or 11/12 works well. We will stick with default or 3.
    custom_config = r'--oem 3 --psm 3'
    raw_text = pytesseract.image_to_string(pil_img, config=custom_config)
    cleaned_text = clean_ocr_text(raw_text)
    
    # Extract word confidence levels
    avg_conf = 0.0
    try:
        data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT, config=custom_config)
        confidences = []
        for i in range(len(data['text'])):
            word = data['text'][i].strip()
            conf = int(data['conf'][i])
            # Filter out empty strings and non-confident indicators (-1)
            if word and conf != -1:
                confidences.append(conf)
                
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            logger.info(f"OCR Word count: {len(confidences)} | Avg Confidence: {avg_conf:.2f}%")
        else:
            logger.warning("No words with valid confidence found in OCR data.")
    except Exception as e:
        logger.error(f"Failed to extract OCR confidence scores: {e}")
        
    return cleaned_text, round(avg_conf, 2)
