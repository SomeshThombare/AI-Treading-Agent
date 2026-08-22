"""
trades/chatbot/image_analyzer.py

Image preprocessing for chart analysis.
Converts uploaded images to PIL format for Gemini Vision.
"""

import io
import logging

logger = logging.getLogger(__name__)


def prepare_image(uploaded_file):
    """
    Convert Django UploadedFile to PIL Image.

    Args:
        uploaded_file: Django UploadedFile object

    Returns:
        PIL Image object or None if conversion fails
    """
    try:
        from PIL import Image
    except ImportError:
        logger.error("Pillow not installed. Run: pip install Pillow")
        return None

    if not uploaded_file:
        return None

    try:
        # Read uploaded file
        image_bytes = uploaded_file.read()

        # Reset file pointer (in case file is read again later)
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(0)

        # Open as PIL Image
        img = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if needed (Gemini requires RGB)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')

        # Resize if too large (>2048px on any side)
        # Gemini Vision works better with reasonable sizes
        max_dimension = 2048
        if img.width > max_dimension or img.height > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            logger.info(f"[IMAGE] Resized to {img.size}")

        logger.info(f"[IMAGE] Prepared image: {img.size}, mode={img.mode}")
        return img

    except Exception as e:
        logger.exception(f"Image preparation failed: {e}")
        return None


def validate_image(uploaded_file):
    """
    Validate uploaded image file.

    Returns:
        (is_valid, error_message)
    """
    if not uploaded_file:
        return False, "No file uploaded"

    # Check file size (max 5MB)
    max_size = 5 * 1024 * 1024  # 5 MB
    if uploaded_file.size > max_size:
        return False, f"Image too large ({uploaded_file.size / 1024 / 1024:.1f}MB). Max 5MB."

    # Check file extension
    name = uploaded_file.name.lower()
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')

    if not any(name.endswith(ext) for ext in valid_extensions):
        return False, "Invalid format. Use JPG, PNG, WEBP, GIF, or BMP."

    return True, None