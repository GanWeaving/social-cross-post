# Standard library imports
import re
import io
import os
import uuid
import time
import shutil
import logging.config
from datetime import datetime

# Third-party imports
from PIL import Image
import pytz
from flask import url_for, flash
import urllib.parse

# Local application/library specific imports
import posthaven
import bluesky
import instagram
import masto
import twitter
import facebook
import configLog
from extensions import db
from models import ScheduledPosts

from app import flask_app

URL_PATTERN = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

# At the top level of helpers.py
logger, speed_logger = configLog.configure_logging()

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

# URL and HTML processing
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

def urls_to_html_links(text_html):
    url_format = '<a href="{}">{}</a>'
    url_matches = list(URL_PATTERN.finditer(text_html))
    for match in reversed(url_matches):
        url = match.group(0)
        start, end = match.span()
        text_html = text_html[:start] + url_format.format(url, url) + text_html[end:]
    return text_html

# Logging
def configure_logging():
    # Set up root logger
    logging.basicConfig(filename='app.log', 
                        format='%(asctime)s %(levelname)s %(module)s:%(lineno)d %(message)s', 
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

# Posting Functions
def try_posting(platform, action, post_data, message_format, *args):
    elapsed_time, _ = timed_execution(action, *args)
    speed_logger.info(f"{platform} post execution time: {elapsed_time} seconds")
    post_data['success_messages'].append(platform)

def send_to_platform(platform, send_func, *args):
    elapsed_time, result = timed_execution(send_func, *args)
    speed_logger.info(f"{platform} upload execution time: {elapsed_time} seconds")
    logger.debug(f'Posting to {platform} completed')
    return bool(result)

def log_and_flash_messages(post_data, success_messages, error_messages):
    success_message = ''
    if success_messages:
        success_message = f'Successfully posted to: {", ".join(success_messages)}.'

    error_message = ''
    if error_messages:
        error_message = f'Failed to post to: {", ".join(error_messages)}.'

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

def send_post(post_data):
    platforms_to_funcs = {
        'Twitter': (twitter.upload_to_twitter, [post_data['image_locations'], post_data['processed_alt_texts'], post_data['text_mastodon']]),
        'Mastodon': (masto.post_to_mastodon, [post_data['subject'], post_data['text_mastodon'], post_data['image_locations'], post_data['processed_alt_texts']]),
        'Bluesky': (bluesky.post_to_bluesky, [post_data['text_mastodon'], post_data['image_locations'], post_data['processed_alt_texts']]),
        'Posthaven': (posthaven.send_email_with_attachments, [post_data['subject'], post_data['text'], post_data['image_locations'], post_data['processed_alt_texts']]),
        'Facebook': (facebook.post_to_facebook, [post_data['image_locations'], post_data['text_mastodon'], post_data['processed_alt_texts']]),
        'Instagram': (instagram.postInstagramCarousel, [post_data['image_locations'], post_data['text']]),
    }

    success_messages = []
    error_messages = []

    for platform, (send_func, args) in platforms_to_funcs.items():
        if post_data[f'enable_{platform.lower()}']:
            result = send_to_platform(platform, send_func, *args)
            if result:
                success_messages.append(platform)
            else:
                error_messages.append(platform)
    
    log_and_flash_messages(post_data, success_messages, error_messages)
    
    # New code to delete the temporary folder after posting images
    for image_location in post_data['image_locations']:
        # Parse the URL to get the path
        url_path = urllib.parse.urlparse(image_location).path
        # Remove the initial slash if there is one
        if url_path.startswith('/'):
            url_path = url_path[1:]
        # Join the path to get the absolute path of the local directory
        dir_path = os.path.join(os.getcwd(), url_path)
        # Get the parent directory of the image file
        parent_dir = os.path.dirname(dir_path)
        # Remove the directory
        if os.path.exists(parent_dir) and os.path.isdir(parent_dir):
            shutil.rmtree(parent_dir)

def create_subject(text):
    now = datetime.now()
    text_stripped = strip_html_tags(text)
    text_preview = text_stripped[:10]
    date_str = now.strftime('%Y/%m/%d')
    subject = f'[{date_str}] {text_preview} ...'
    return subject

def convert_to_utc(time, timezone='Europe/Berlin'):
    try:
        tz = pytz.timezone(timezone)
        return time.astimezone(pytz.utc)
    except Exception as e:
        logger.exception('Error occurred while converting scheduled time: %s', e)
        return None
    
def save_post_to_database(post_data):
    scheduled_time = post_data.get('scheduled_time')

    if scheduled_time:
        utc_scheduled_time = convert_to_utc(scheduled_time)
        if utc_scheduled_time is None:
            return

        # Remove processed_files from the post_data
        post_data.pop('processed_files', None)

        post = ScheduledPosts(text=post_data.get('text'), scheduled_time=utc_scheduled_time, post_data=post_data)
        try:
            with db.session.begin():
                db.session.add(post)
            logger.info('Post saved to the database.')
            flash('Post has been scheduled!')
        except Exception as e:
            logger.exception('Error occurred while saving post to the database: %s', e)
            flash(f'Scheduling has failed! error: {e}')
            return None

        return post
    else:
        logger.info('Scheduled time is not provided. Posting immediately.')


def send_scheduled_post(post_id):
    logger.debug('send_scheduled_post function triggered')

    with flask_app.app_context():
        post = ScheduledPosts.query.get(post_id)

        if not post or post.posted:
            return

        current_time = datetime.now(pytz.utc)
        scheduled_time = post.scheduled_time
        scheduled_time = scheduled_time.astimezone(pytz.utc)

        if scheduled_time <= current_time:
            post_data = post.post_data

            logger.debug(f"Attempting to send Post {post.id}")
            try:
                send_post(post_data)
                logger.debug(f"Post {post.id} has been successfully sent.")
            except Exception as e:
                logger.error(f"Error occurred while sending Post {post.id}: {str(e)}")
                return

            logger.debug(f"Attempting to delete Post {post.id} from the database")
            try:
                db.session.delete(post)
                db.session.commit()
                logger.debug(f"Post {post.id} has been posted and deleted from the database.")
            except Exception as e:
                logger.error(f"Error occurred while deleting Post {post.id} from the database: {str(e)}")
                return

            deleted_post = ScheduledPosts.query.get(post.id)
            assert deleted_post is None, f"Post {post.id} has not been deleted from the database"
        else:
            logger.debug(f"Post {post.id} is not yet due to be posted.")

def timed_execution(function, *args, **kwargs):
    start = time.time()
    result = function(*args, **kwargs)
    end = time.time()
    return end - start, result

def create_temp_dir(app, scheduled_time):
    temp_dir = os.path.join(app.root_path, 'static/temp')

    # If scheduled_time is not provided, use the current time
    if not scheduled_time:
        scheduled_time = datetime.now()

    scheduled_folder = scheduled_time.strftime("%Y%m%d_%H%M%S")
    temp_dir = os.path.join(temp_dir, scheduled_folder)
    os.makedirs(temp_dir, exist_ok=True)

    return temp_dir

def process_files(app, files, alt_texts, new_names, scheduled_time):

    if not files or files[0].filename == '':
        return [], [], []

    processed_files = []
    processed_alt_texts = []
    image_locations = []

    temp_dir = create_temp_dir(app, scheduled_time)
    files, alt_texts, new_names = sort_files_by_new_names(files, alt_texts, new_names)

    files, alt_texts, new_names = sort_files_by_new_names(files, alt_texts, new_names)

    for (file, alt_text, new_name) in zip(files, alt_texts, new_names):
        try:
            image = Image.open(file).convert("RGB")

            # If a new name has been entered, use it; otherwise, generate a random name.
            if new_name and new_name != '':
                filename = urllib.parse.quote(new_name) + '.jpg'
            else:
                filename = str(uuid.uuid4()) + '.jpg'

            temp_file_path = os.path.join(temp_dir, filename)

            image.save(temp_file_path, 'JPEG', quality=90)

            image_url = url_for('static', filename=f'{temp_dir}/{filename}', _external=True)

            image_locations.append(image_url)
            logger.debug(f"Image locations: {image_locations}")

            with open(temp_file_path, 'rb') as img_file:
                processed_files.append((temp_file_path, resize_image(img_file)))
            processed_alt_texts.append(alt_text)

        except Exception as e:
            logger.error(f"Unable to process one of the attachments. Error: {e}")
            raise

    return processed_files, processed_alt_texts, image_locations

def sort_files_by_new_names(files, alt_texts, new_names):
    return zip(*sorted(zip(files, alt_texts, new_names), 
                  key=lambda x: x[2] if x[2] and x[2] != '' else x[0].filename))