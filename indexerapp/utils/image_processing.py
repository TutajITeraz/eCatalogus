# utils/image_processing.py
"""
Utility module for image processing – mainly downscaling raster images
stored in Django FileField/ImageField objects.
Supported formats: JPEG, PNG, GIF, WEBP, BMP.
"""

from PIL import Image, UnidentifiedImageError
import io
import os
from django.core.files.base import ContentFile


def downscale_if_raster(image_field_file, max_long_edge: int = 300) -> bool:
    """
    Downscales a raster image in-place if its longer edge exceeds max_long_edge.
    Overwrites the ORIGINAL file on disk – no duplicates, no suffixes, no nested folders.

    Args:
        image_field_file: Django ImageFieldFile / FileField instance
        max_long_edge (int): Maximum allowed length of the longer edge after resizing

    Returns:
        bool: True if the image was resized and saved, False otherwise
    """
    if not image_field_file:
        return False

    # Full storage path (e.g. "images/883-3_aj9rOT5.jpg")
    original_name = image_field_file.name
    # Filename only – this is what Django expects when we want to keep the same location
    filename_only = os.path.basename(original_name)

    # Reset file pointer (important when the file has been read before)
    image_field_file.seek(0)

    try:
        # Open image and make a copy (PIL may modify the original object)
        img = Image.open(image_field_file)
        img = img.copy()
        image_field_file.seek(0)

        # Determine format – PIL sometimes leaves img.format as None
        format = img.format
        if format is None:
            header = image_field_file.read(12)
            image_field_file.seek(0)
            if header.startswith(b'\x89PNG'):
                format = 'PNG'
            elif header.startswith((b'\xff\xd8\xff',)):
                format = 'JPEG'
            elif header.startswith(b'RIFF') and header[8:12] == b'WEBP':
                format = 'WEBP'
            elif header.startswith(b'BM'):
                format = 'BMP'
            elif header.startswith((b'GIF87a', b'GIF89a')):
                format = 'GIF'
            else:
                return False

        format = format.upper()
        if format not in {'JPEG', 'PNG', 'GIF', 'WEBP', 'BMP'}:
            return False

        # No need to resize if already small enough
        width, height = img.size
        if max(width, height) <= max_long_edge:
            return False

        # Calculate new dimensions while preserving aspect ratio
        ratio = max_long_edge / max(width, height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Prepare in-memory buffer
        buffer = io.BytesIO()

        # Format-specific conversion and save options
        save_kwargs = {}

        if format == 'JPEG':
            # JPEG does not support alpha → convert and add white background if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                mask = img.split()[-1] if img.mode in ('RGBA', 'LA') else None
                bg.paste(img, mask=mask)
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            save_kwargs = {'quality': 90, 'optimize': True, 'progressive': True}

        elif format == 'PNG':
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA')
            save_kwargs = {'optimize': True, 'compress_level': 6}

        elif format == 'WEBP':
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA' if 'A' in img.mode else 'RGB')
            save_kwargs = {'quality': 90, 'method': 6}

        elif format == 'GIF':
            save_kwargs = {'optimize': True, 'interlace': True}

        elif format == 'BMP':
            if img.mode != 'RGB':
                img = img.convert('RGB')

        # Save resized image to buffer
        img.save(buffer, format=format, **save_kwargs)
        buffer.seek(0)

        # CRITICAL PART: overwrite the original file correctly
        # 1. Delete the old physical file (prevents duplicates)
        if image_field_file.storage.exists(original_name):
            image_field_file.storage.delete(original_name)
            print(f"Deleted old file: {original_name}")

        # 2. Save new content using only the filename → Django puts it in the correct upload_to folder
        image_field_file.save(
            filename_only,
            ContentFile(buffer.getvalue()),
            save=False  # Do not trigger model save signals
        )

        print(f"Overwritten: {original_name} → new size {img.size}")
        return True

    except UnidentifiedImageError:
        print(f"Error: Unidentified image format – {original_name}")
        return False
    except Exception as e:
        print(f"Error processing image {original_name}: {e}")
        return False
    finally:
        # Always reset file pointer
        try:
            image_field_file.seek(0)
        except Exception:
            pass


def get_image_info(image_field_file) -> dict:
    """
    Returns basic information about an image without modifying it.
    """
    if not image_field_file:
        return {}

    try:
        image_field_file.seek(0)
        with Image.open(image_field_file) as img:
            info = {
                'width': img.width,
                'height': img.height,
                'format': img.format or 'UNKNOWN',
                'size_bytes': image_field_file.size,
                'mode': img.mode,
            }
        image_field_file.seek(0)
        return info
    except Exception:
        return {}


def is_raster_image(image_field_file) -> bool:
    """
    Checks whether the file is a raster image (JPEG/PNG/GIF/WEBP/BMP).
    """
    if not image_field_file:
        return False

    try:
        image_field_file.seek(0)
        with Image.open(image_field_file) as img:
            result = img.format in {'JPEG', 'PNG', 'GIF', 'WEBP', 'BMP'}
        image_field_file.seek(0)
        return result
    except Exception:
        return False