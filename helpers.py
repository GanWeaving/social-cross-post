import re
import io
import os
import glob
from PIL import Image
import logging
import posthaven
import bluesky
import instagram
import masto
import twitter
import facebook
import inspect
import time 
from flask import url_for, flash
import shutil

logger = logging.getLogger()
speed_logger = logging.getLogger('speed_logger')

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
            try:
                os.remove(file)
                logger.debug(f"Deleted file: {file}")
            except Exception as e:
                logger.error(f"Failed to delete file {file}. Error: {e}")


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

def try_posting(platform, action, post_data, message_format, *args):
    start = time.time()
    try:
        logger.debug(message_format, ', '.join(post_data['image_locations']))
        action(*args)
        end = time.time()
        speed_logger.info(f"{platform} post execution time: {end - start} seconds")
        logger.debug(f'Posting to {platform} completed')
        post_data['success_messages'].append(platform)
    except Exception as e:
        logger.error(f'Failed to post to {platform}. Error: %s', e)
        post_data['error_messages'].append(platform)

def send_post(post_data):
    post_data['success_messages'] = []
    post_data['error_messages'] = []

    if post_data['enable_twitter']:
        args = [post_data['image_locations'], post_data['processed_alt_texts'], post_data['text_mastodon']]
        try_posting('Twitter', twitter.upload_to_twitter, post_data, 'Posting to Twitter: %s', *args)

    if post_data['enable_mastodon']:
        args = [post_data['subject'], post_data['text_mastodon'], post_data['image_locations'], post_data['processed_alt_texts']]
        try_posting('Mastodon', masto.post_to_mastodon, post_data, 'Posting to Mastodon: %s', *args)

    if post_data['enable_bluesky']:
        bluesky.login_to_bluesky()
        args = [post_data['text_mastodon'], post_data['image_locations'], post_data['processed_alt_texts']]
        try_posting('Bluesky', bluesky.post_to_bluesky, post_data, 'Posting to Bluesky: %s images', *args)

    if post_data['enable_posthaven']:
        args = [post_data['subject'], post_data['text'], post_data['image_locations'], post_data['processed_alt_texts']]
        try_posting('Posthaven', posthaven.send_email_with_attachments, post_data, 'Sending email: %s', *args)

    if post_data['enable_facebook']:
        args = [post_data['image_locations'], post_data['text_mastodon'], post_data['processed_alt_texts']]
        try_posting('Facebook', facebook.post_to_facebook, post_data, 'Posting to Facebook: %s', *args)

    if post_data['enable_instagram']:
        args = [post_data['image_locations'], post_data['text']]
        try_posting('Instagram', instagram.postInstagramCarousel, post_data, 'Posting to Instagram: %s', *args)

    try:
            logger.debug('Trying to delete media files')

            # Extract directory from one of the image locations
            directory = None
            if post_data['image_locations']:
                # Assume image_locations[0] is a URL that includes the base URL
                # 'http://post.int0thec0de.xyz/' and replace it with ''
                local_path = post_data['image_locations'][0].replace('http://post.int0thec0de.xyz/', '')
                directory = os.path.dirname(local_path)

            if directory:
                shutil.rmtree(directory)
                logger.debug(f'Deleted directory {directory}')
                
    except Exception as e:
        error_message = f'Failed to delete media files. Error: {e}'
        line_number = inspect.currentframe().f_lineno
        logger.error(f'{error_message} (Line: {line_number})')

    success_message = ''
    if post_data['success_messages']:
        success_message = f'Successfully posted to: {", ".join(post_data["success_messages"])}.'

    error_message = ''
    if post_data['error_messages']:
        error_message = f'Failed to post to: {", ".join(post_data["error_messages"])}.'

    if post_data.get('scheduled_time'):
        if success_message and error_message:
            logger.debug(f'{success_message} {error_message}')
        elif success_message:
            logger.debug(success_message)
        elif error_message:
            logger.debug(error_message)
    else:
        if success_message and error_message:
            flash(f'{success_message} {error_message}')
        elif success_message:
            flash(success_message)
        elif error_message:
            flash(error_message)
