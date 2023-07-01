from tweepy import Client
import json
import requests
import helpers
from requests_oauthlib import OAuth1
from urllib.parse import urlparse
import configLog

logger, speed_logger = configLog.configure_logging()

# Load Twitter credentials from config.json
with open("config.json", "r") as file:
    twitter_config = json.load(file)

# OAuth1 authentication
auth = OAuth1(
    twitter_config["consumer_key"],
    twitter_config["consumer_secret"],
    twitter_config["access_token"],
    twitter_config["access_token_secret"],
)

# Create client object
client = Client(
    consumer_key=twitter_config["consumer_key"],
    consumer_secret=twitter_config["consumer_secret"],
    access_token=twitter_config["access_token"],
    access_token_secret=twitter_config["access_token_secret"],
)

def upload_to_twitter(image_locations, alt_texts, text):
    try:
        if image_locations:
            media_ids = []
            for image_location, alt_text in zip(image_locations, alt_texts):
                # Parse the URL and get the path
                url_parts = urlparse(image_location)
                local_file_path = url_parts.path[1:]  # Remove the leading '/'

                # Get media id
                media_id = upload_local_image(local_file_path, twitter_config, alt_text)
                if not media_id:  # if media upload failed
                    return False
                media_ids.append(media_id)
            
            tweet_text = helpers.strip_html_tags(text)  # Customize as required
            tweet_text = text.replace("[prompt in the alt]", "[prompts over on Bluesky & Mastodon]")  # Replace the string
            res = client.create_tweet(text=tweet_text, media_ids=media_ids)
        else:
            tweet_text = helpers.strip_html_tags(text)
            tweet_text = text.replace("[prompt in the alt]", "[prompts over on Bluesky & Mastodon]")
            res = client.create_tweet(text=tweet_text)
    except Exception as e:
        logger.exception(f"Failed to post to Twitter. Error: {e}")
        return False

    return True if res else False  # Return True if the tweet is created successfully, False otherwise

def upload_local_image(filepath, config, alt_text):
    # Endpoint URL
    url = 'https://upload.twitter.com/1.1/media/upload.json'
   
    # File to upload
    try:
        files = {'media': open(filepath, 'rb')}
    except Exception as e:
        logger.exception(f"Failed to open file {filepath}. Exception: {e}")
        return None

    #logger.debug(f'Opened file {filepath}.')
    
    # Additional parameters
    params = {'media_category': 'TWEET_IMAGE'}

    # Making the POST request
    try:
        response = requests.post(url, files=files, params=params, auth=auth)
        response.raise_for_status()
    except Exception as e:
        logger.exception(f"POST request failed. Exception: {e}")
        return None

    logger.debug(f'POST request to {url} successful. HTTP status code: {response.status_code}')

    # Output the response (for debugging purposes)
    json_res = response.json()
    logger.debug(f"Received Media ID: {json_res['media_id']}")

    return json_res["media_id"]
