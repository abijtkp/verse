from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image


ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'webp', 'avif']


def optimize_variant_image(image_file, max_size=(1200, 1200), quality=85):

    extension = image_file.name.split('.')[-1].lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            'Unsupported image format. Please upload JPG, JPEG, PNG, WEBP or AVIF images.'
        )

    image = Image.open(image_file)

    if image.mode in ("RGBA", "P", "LA"):
        image = image.convert("RGB")

    image.thumbnail(max_size)

    output = BytesIO()

    image.save(
        output,
        format='JPEG',
        quality=quality,
        optimize=True
    )

    output.seek(0)

    original_name = image_file.name.rsplit('.', 1)[0]
    new_name = f"{original_name}.jpg"

    return ContentFile(output.read(), name=new_name)