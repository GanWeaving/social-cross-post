import re
import io
import os
import glob
from PIL import Image
import logging

logger = logging.getLogger()

URL_PATTERN = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

def strip_html_tags(text):
    return re.sub('<[^<]+?>', '', text)
    
def resize_image(image_file, max_size_kb=976.56, max_iterations=10):
    with Image.open(image_file) as img:
        img_format = 'JPEG'
        for _ in range(max_iterations):
            img_data = io.BytesIO()
            img.save(img_data, img_format)
            size_kb = len(img_data.getvalue()) / 1024

            if size_kb <= max_size_kb:
                return img_data.getvalue()

            quality = int(max((1 - (size_kb - max_size_kb) / size_kb) * 100, 0))
            img.save(img_data, img_format, quality=quality)

        raise ValueError(f"Could not reduce image size below {max_size_kb}KB")

def delete_images_from_static(processed_files):
    for file_path, _ in processed_files:
        try:
            os.remove(file_path)
            logger.info('Deleted file: %s', file_path)
        except Exception as e:
            logger.error(f'Failed to delete file {file_path}. Error: {e}')

def generate_facets_from_links_in_text(text):
    return [gen_link(*match.span(), match.group(0)) for match in URL_PATTERN.finditer(text)]

def gen_link(start, end, uri):
    return gen_range(start, end, [{
        "$type": "app.bsky.richtext.facet#link",
        "uri": uri
    }])

def gen_range(start, end, features):
    return {
        "index": {
            "byteStart": start,
            "byteEnd": end
        },
        "features": features
    }

def delete_media_files_in_directory(directory):
    file_types = ['*.jpg', '*.png', '*.jpeg', '*.gif']
    for file_type in file_types:
        for file in glob.glob(os.path.join(directory, file_type)):
            os.remove(file)

def urls_to_html_links(text_html):
    url_format = '<a href="{}">{}</a>'
    url_matches = list(URL_PATTERN.finditer(text_html))

    for match in reversed(url_matches):
        url = match.group(0)
        start, end = match.span()
        text_html = text_html[:start] + url_format.format(url, url) + text_html[end:]

    return text_html

def configure_logging():
    # Set up root logger
    logging.basicConfig(filename='app.log', 
                        format='%(asctime)s %(levelname)s %(name)s %(message)s', 
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.DEBUG)

    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # This is your general logger
    logger = logging.getLogger()

    # Set up logging for speed measurements
    speed_logger = logging.getLogger('speed_logger')
    speed_logger.setLevel(logging.INFO)

    handler = logging.FileHandler('speed.log')
    handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler.setFormatter(formatter)

    speed_logger.addHandler(handler)

    # Return both loggers
    return logger, speed_logger

