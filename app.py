import os
import pytz
import logging
from PIL import Image
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_session import Session  # if you're using flask-session

# Custom modules
import helpers
import posthaven
import bluesky
import instagram
import masto
import twitter
from config import Config, MYPASSWORD

# Get the filename of the current module
logname = os.path.splitext(os.path.basename(__file__))[0]

# Set up root logger
logging.basicConfig(filename='app.log', 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s', 
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.DEBUG)

# Now you can get that logger with logging.getLogger() without arguments
logger = logging.getLogger()

# List of URLs or locations of your images
image_locations = []

app = Flask(__name__)
app.config.from_object(Config)
Session(app)

@app.route('/')
def index():
    logger.info('Index page loaded')
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == MYPASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return "Incorrect password, try again."
    return render_template('login.html')

@app.route('/submit', methods=['POST'])
def submit_form():
    bluesky.login_to_bluesky()
    text = request.form['text']
    text_html = "<br>".join(text.splitlines())  # Convert line breaks to <br> tags
    text_html = helpers.urls_to_html_links(text_html)  # Convert URLs to links

    hashtag = request.form.get('hashtagCheckbox')  # get the value of hashtagCheckbox
    hashtag_text = request.form.get('txt_hashtags')  # get the value of txt_hashtags
    alt_text_checkbox = request.form.get('altCheckbox')  # get the value of altCheckbox
    logger.info("alt_text_checkbox: %s", alt_text_checkbox)  # log the value for debugging

    if alt_text_checkbox:  # if checkbox is checked, add '[prompt in the alt]'
        text += '\n\n[prompt in the alt]'

    if hashtag == 'on':  # if checkbox is checked, append hashtag_text
        text += '\n\n' + hashtag_text

    text_mastodon = "\n".join(text.splitlines())  # Convert line breaks to \n for Mastodon
    
    text = f'<big>{text_html}</big><hr>'

    files = request.files.getlist('files')
    logger.info('files: %s', files)

    if files:  # this block will execute if any files have been uploaded
        new_names = [request.form.get('new_name_' + str(i)) for i in range(len(files))]
        logger.info('new names: %s', new_names)

        # Rename files by appending the extension of the current filename
        for i, file in enumerate(files):
            filename, extension = os.path.splitext(file.filename)
            new_name = new_names[i] + extension if new_names[i] and new_names[i] != '' else filename + extension
            file.filename = new_name
            logger.info('file.filename: %s', file.filename)

        # Get alt texts
        alt_texts = [request.form.get('alt_text_' + str(i)) for i in range(len(files))]

        # Combine files and alt_texts into a list of tuples
        file_alt_text_pairs = list(zip(files, alt_texts))

        # Sort the list of tuples by the new file names
        file_alt_text_pairs.sort(key=lambda pair: pair[0].filename)
        logger.info('sorted file pairs: %s', file_alt_text_pairs)

        # Unzip the list of tuples back into files and alt_texts using list comprehensions
        files, alt_texts = [list(t) for t in zip(*file_alt_text_pairs)]

        # Error handling for file upload limit
        if len(files) > 4:
            flash('Error: Maximum of 4 files are allowed.')
            return redirect(url_for('index'))

        # Process files and store resized images
        processed_files, processed_alt_texts = process_files(files, alt_texts)
        logger.debug('Files after processing: %s', ', '.join(filename for filename, _ in processed_files))

        try:
            twitter.upload_to_twitter(processed_files, alt_texts, text_mastodon)
            #logger.debug('processed files: %s', processed_files)
            #logger.debug('Posting to Twitter completed')
        except Exception as e:
            flash(f'Failed to post to Twitter. Error: {e}')

        # Post carousel to Instagram
        try:
            logger.debug('Image locations: %s', image_locations)
            instagram.postInstagramCarousel(image_locations, text)
            logger.debug('Posting to Instagram completed')
            #delete_images_from_static(processed_files)  # Delete the images from the static directory
        except Exception as e:
            flash(f'Failed to post to Instagram. Error: {e}')

    else:
        processed_files = []
        alt_texts = []

    # Create the email subject
    timezone = pytz.timezone('Europe/Berlin')  # Replace 'Your_Timezone' with your desired timezone
    now = datetime.now(timezone)
    # Extract the first 10 characters from the 'text' field
    text_preview = helpers.strip_html_tags(text[:10])
    # Format the current time as 'year/month/day'
    date_str = now.strftime('%Y/%m/%d')
    # Create the subject string
    subject = f'[{date_str}] {text_preview} ...'
   
    # Process files and send email
    try:
        logger.debug('Sending email: %s', ', '.join(filename for filename, _ in processed_files))
        posthaven.send_email_with_attachments(subject, text, processed_files, alt_texts)
        logger.debug('Sending email completed')
        logger.debug('Posting to Mastodon: %s', ', '.join(filename for filename, _ in processed_files))
        masto.post_to_mastodon(subject, text_mastodon, processed_files, alt_texts)
        logger.debug('Posting to Mastodon completed')
        logger.debug('Posting to Bluesky: %s', ', '.join(filename for filename, _ in processed_files))
        bluesky.post_to_bluesky(text_mastodon, processed_files, alt_texts)
        logger.debug('Posting to Bluesky completed')
        flash('Email sent successfully! Content posted to Mastodon and Bluesky.')
        helpers.delete_media_files_in_directory('.')
        helpers.delete_media_files_in_directory('temp')
    except Exception as e:
        flash(f'Failed to send email or post to Mastodon or Bluesky. Error: {e}')

    return redirect(url_for('index'))

def process_files(files, alt_texts):
    if not files or files[0].filename == '':
        return [], []  

    processed_files = []
    processed_alt_texts = []
    temp_dir = os.path.join(app.root_path, 'temp')
    base_url = "https://post.int0thec0de.xyz/temp/"

    for (file, alt_text) in zip(files, alt_texts):
        try:
            image = Image.open(file).convert("RGB")
            filename = os.path.splitext(file.filename)[0] + '.jpg'
            temp_file_path = os.path.join(temp_dir, filename)
            
            image.save(temp_file_path, 'JPEG', quality=90)
            logger.info('Saved processed image: %s', temp_file_path)

            image_url = base_url + filename
            image_locations.append(image_url)
            logger.info('Appended image URL: %s', image_url)
            logger.info('content of image_locations: %s', image_locations)
            
            with open(temp_file_path, 'rb') as img_file:
                processed_files.append((temp_file_path, helpers.resize_image(img_file)))
            processed_alt_texts.append(alt_text)
            logger.info('Processed file: %s', temp_file_path)

        except Exception as e:
            flash(f"Unable to process one of the attachments. Error: {e}")
            raise

    return processed_files, processed_alt_texts


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)