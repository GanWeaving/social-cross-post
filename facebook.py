import requests
import json
import logging
from typing import List, Optional
from config import (FB_ACCESS_TOKEN, FB_PAGE_ID)
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger()

# Constants for Facebook URLs
IMAGE_URL = f'https://graph.facebook.com/{FB_PAGE_ID}/photos'
FEED_URL = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"

def upload_image_to_fb(image_location: str) -> Optional[str]:
    payload = {
        'url': image_location,
        'access_token': FB_ACCESS_TOKEN,
        'published': 'false'
    }
    r = requests.post(IMAGE_URL, data=payload)
    if r.status_code != 200:
        logger.error(f"Failed to upload image: {image_location}. Error: {r.text}")
        return None
    photo_id = r.json()['id']
    logger.info(f"Image uploaded successfully: {image_location}")
    logger.debug(f"uploaded photo id: {photo_id}")
    return photo_id

def upload_images_to_fb(image_locations: List[str]) -> List[str]:
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(upload_image_to_fb, image_location) for image_location in image_locations}
        uploaded_photo_ids = [future.result() for future in futures if future.result() is not None]
    return uploaded_photo_ids

def post_to_facebook(image_locations: List[str], text: str, alt_texts: Optional[List[str]] = None) -> bool:
    if alt_texts:
        alt_text_str = "\n\n".join(filter(None, alt_texts))  # Filter out empty alt texts and join them with line breaks
        text = text.replace("[prompt in the alt]", "[image prompts below]") + "\n\n" + alt_text_str
    uploaded_photo_ids = upload_images_to_fb(image_locations)
    payload = {
        'access_token': FB_ACCESS_TOKEN,
        'message': text,  # Assuming the function helpers.strip_html_tags() was removed for a reason
    }
    if uploaded_photo_ids:
        attached_media = [{"media_fbid": photo_id} for photo_id in uploaded_photo_ids]
        payload['attached_media'] = json.dumps(attached_media)
    r = requests.post(FEED_URL, data=payload)
    if r.status_code != 200:
        logger.error(f"Failed to publish post. Error: {r.text}")
        return False
    logger.info("Post published successfully!")
    return True
