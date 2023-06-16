import requests
import json
import logging
import helpers
from config import (FB_ACCESS_TOKEN, FB_PAGE_ID)

logger = logging.getLogger()

# Your Access Keys
page_id = FB_PAGE_ID

# Your Page Access Token
facebook_access_token = FB_ACCESS_TOKEN

def upload_images_to_fb(image_locations):
    image_url = 'https://graph.facebook.com/{}/photos'.format(page_id)
    uploaded_photo_ids = []
    for image_location in image_locations:
        img_payload = {
            'url': image_location,
            'access_token': facebook_access_token,
            'published': 'false'
        }
        # Upload the image unpublished
        r = requests.post(image_url, data=img_payload)
        if r.status_code == 200:
            logger.info(f"Image uploaded successfully: {image_location}")
            photo_id = json.loads(r.text)['id']
            uploaded_photo_ids.append(photo_id)
        else:
            logger.error(f"Failed to upload image: {image_location}. Error: {r.text}")
        logger.error(f"uploaded photos ids: {uploaded_photo_ids}")
    return uploaded_photo_ids

def post_to_facebook(image_locations, text):

    uploaded_photo_ids = upload_images_to_fb(image_locations)
    
    # Create a multi-photo post
    feed_url = f"https://graph.facebook.com/{page_id}/feed"
    feed_payload = {
        'access_token': facebook_access_token,
        'message': helpers.strip_html_tags(text)
    }
    for i, photo_id in enumerate(uploaded_photo_ids):
        feed_payload[f'attached_media[{i}]'] = json.dumps({"media_fbid": photo_id})

    r = requests.post(feed_url, data=feed_payload)
    if r.status_code == 200:
        logger.info("Multi-photo post published successfully!")
        return True
    else:
        logger.error(f"Failed to publish post. Error: {r.text}")
        return False

