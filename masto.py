from mastodon import Mastodon
import logging
from urllib.parse import urlparse
from config import (MASTODON_ACCESS_TOKEN, MASTODON_API_BASE_URL)

logger = logging.getLogger()

def post_to_mastodon(subject, body, image_locations, alt_texts):
    mastodon = Mastodon(
        access_token=MASTODON_ACCESS_TOKEN,
        api_base_url=MASTODON_API_BASE_URL
    )

    media_ids = []
    for idx, image_location in enumerate(image_locations):
        try:
            # Parse the URL and get the path
            url_parts = urlparse(image_location)
            local_file_path = url_parts.path[1:]  # Remove the leading '/'

            # Open the image file from its location
            with open(local_file_path, "rb") as image_file:
                media = mastodon.media_post(image_file.read(), mime_type='image/jpeg', description=alt_texts[idx])
                media_ids.append(media['id'])

        except Exception as e:
            logger.exception(f"Unable to process one of the attachments for Mastodon. Error: {e}")
            raise

    if media_ids:  # Check if there are media attachments
        mastodon.status_post(body, media_ids=media_ids)
    else:
        mastodon.status_post(body)
