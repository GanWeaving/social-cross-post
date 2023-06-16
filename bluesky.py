import helpers
import logging
from atproto import Client, models
from datetime import datetime
from config import (BLUESKY_EMAIL, BLUESKY_PASSWORD)

logger = logging.getLogger()

client = Client()

def login_to_bluesky():
    global client
    try:
        client.login(BLUESKY_EMAIL, BLUESKY_PASSWORD)
        logger.debug("Successfully logged in to Bluesky.")
    except Exception as e:
        logger.error(f"Failed to log in to Bluesky: {e}")

def post_to_bluesky(text, processed_files, alt_texts):
    login_to_bluesky()
    text = helpers.strip_html_tags(text)
    logger.debug(f"Stripped text: {text}")
    
    images = []
    for idx, (filename, img_data) in enumerate(processed_files):
        alt_text = alt_texts[idx] if idx < len(alt_texts) else ""
        upload = client.com.atproto.repo.upload_blob(img_data)
        images.append(models.AppBskyEmbedImages.Image(alt=alt_text, image=upload.blob))
        logger.debug(f"Uploaded image: {upload.blob}")

    embed = models.AppBskyEmbedImages.Main(images=images) if images else None
    facets = helpers.generate_facets_from_links_in_text(text) if helpers.URL_PATTERN.search(text) else None
    logger.debug(f"Embed: {embed}, Facets: {facets}")

    client.com.atproto.repo.create_record(
        models.ComAtprotoRepoCreateRecord.Data(
            repo=client.me.did,
            collection='app.bsky.feed.post',
            record=models.AppBskyFeedPost.Main(
                createdAt=datetime.now().isoformat(), text=text, embed=embed, facets=facets
            ),
        )
    )
    logger.debug("Bluesky post created.")
