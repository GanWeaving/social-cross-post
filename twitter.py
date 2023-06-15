from tweepy import Client
import json
import requests
import logging
import helpers
from requests_oauthlib import OAuth1

logger = logging.getLogger()

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

def upload_to_twitter(processed_files, alt_texts, text):
    if processed_files:  
        media_ids = []
        for filepath, alt_text in zip(processed_files, alt_texts):
            # get media id
            media_id = upload_local_image(filepath[0], twitter_config, alt_text)
            logger.debug(f"Uploaded file: {filepath[0]}, Media ID: {media_id}")
            media_ids.append(media_id)
        
        tweet_text = helpers.strip_html_tags(text)  # Customize as required
        tweet_text = text.replace("[prompt in the alt]", "[prompts over on Bluesky & Mastodon]")  # Replace the string
        logger.debug(f"Creating tweet: {tweet_text}")
        res = client.create_tweet(text=tweet_text, media_ids=media_ids)
        logger.debug(f"Posted to Twitter with response: {res}")
        return res
    else:
        tweet_text = helpers.strip_html_tags(text)
        tweet_text = text.replace("[prompt in the alt]", "[prompts over on Bluesky & Mastodon]")
        logger.debug(f"Creating tweet: {tweet_text}")
        res = client.create_tweet(text=tweet_text)
        logger.debug(f"Posted to Twitter with response: {res}")
        return res

def upload_local_image(filepath, config, alt_text):
    # Endpoint URL
    url = 'https://upload.twitter.com/1.1/media/upload.json'
   
    # File to upload
    try:
        files = {'media': open(filepath, 'rb')}
    except Exception as e:
        logger.error(f"Failed to open file {filepath}. Exception: {e}")
        raise

    logger.debug(f'Opened file {filepath}.')
    
    # Additional parameters
    params = {'media_category': 'TWEET_IMAGE'}

    # Making the POST request
    try:
        response = requests.post(url, files=files, params=params, auth=auth)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"POST request failed. Exception: {e}")
        raise

    logger.debug(f'POST request to {url} successful. HTTP status code: {response.status_code}')

    # Output the response (for debugging purposes)
    json_res = response.json()
    logger.debug(f"Received Media ID: {json_res['media_id']}")

    return json_res["media_id"]