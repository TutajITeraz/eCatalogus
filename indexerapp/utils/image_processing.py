# utils/image_processing.py
from PIL import Image, UnidentifiedImageError
import io
import os
from django.core.files.base import ContentFile


def downscale_if_raster(image_field_file, max_long_edge: int = 300) -> bool:
    """
    Resizes raster image in-place if longer edge exceeds max_long_edge.
    Always overwrites the ORIGINAL file (no duplicate folders!).
    """
    if not image_field_file:
        return False

    # Store original position and name
    original_name = image_field_file.name  # e.g. "images/883-3_aj9rOT5.jpg"
    image_field_file.seek(0)

    try:
        img = Image.open(image_field_file)
        img = img.copy()
        image_field_file.seek(0)

        # Detect format from content
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

        width, height = img.size
        if max(width, height) <= max_long_edge:
            return False

        # Resize
        ratio = max_long_edge / max(width, height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

        # Prepare buffer
        buffer = io.BytesIO()

        save_kwargs = {}
        if format == 'JPEG':
            if img.mode in ('RGBA', 'LA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            save_kwargs = {'quality': 90, 'optimize': True}

        elif format == 'PNG':
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA')
            save_kwargs = {'optimize': True}

        elif format == 'WEBP':
            save_kwargs = {'quality': 90, 'method': 6}
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGBA' if 'A' in img.mode else 'RGB')

        elif format == 'GIF':
            save_kwargs = {'optimize': True}

        img.save(buffer, format=format, **save_kwargs)
        buffer.seek(0)

        # CRITICAL FIX: Use only the filename, not the full path
        filename = os.path.basename(original_name)

        # Overwrite the original file using the correct name
        image_field_file.save(filename, ContentFile(buffer.read()), save=False)
        return True

    except UnidentifiedImageError:
        return False
    except Exception as e:
        print(f"Error processing image {original_name}: {e}")
        return False
    finally:
        try:
            image_field_file.seek(0)
        except:
            pass