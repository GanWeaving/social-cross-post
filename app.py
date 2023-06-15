import os
import pytz
import logging
from PIL import Image
from datetime import datetime
import inspect
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

enable_twitter = False
enable_instagram = True
enable_posthaven = False
enable_bluesky = False
enable_mastodon = False

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

    # Check if any images have been selected and if any of them have alt text
    files = request.files.getlist('files')
    alt_texts = [request.form.get('alt_text_' + str(i)) for i in range(len(files))]
    if files and any(alt_texts):
        text += '\n\n[prompt in the alt]'

    if hashtag == 'on':  # if checkbox is checked, append hashtag_text
        text += '\n\n' + hashtag_text

    text_mastodon = "\n".join(text.splitlines())  # Convert line breaks to \n for Mastodon
    
    text = f'<big>{text_html}</big><hr>'

    files = request.files.getlist('files')
    logger.info('files: %s', files)
    textOnly = False

    if files:  # this block will execute if any files have been uploaded
        new_names = [request.form.get('new_name_' + str(i)) for i in range(len(files))]
        logger.info('new names: %s', new_names)

        # Rename files by appending the extension of the current filename or keep the original filename
        for i, file in enumerate(files):
            filename, extension = os.path.splitext(file.filename)
            new_name = new_names[i] + extension if new_names[i] and new_names[i] != '' else filename
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
    else:
        processed_files = []
        processed_alt_texts = []
        textOnly = True

    # Create the email subject
    timezone = pytz.timezone('Europe/Berlin')  # Replace 'Your_Timezone' with your desired timezone
    now = datetime.now(timezone)
    # Extract the first 10 characters from the 'text' field
    text_preview = helpers.strip_html_tags(text[:10])
    # Format the current time as 'year/month/day'
    date_str = now.strftime('%Y/%m/%d')
    # Create the subject string
    subject = f'[{date_str}] {text_preview} ...'

    # Update the enable variables based on checkbox values
    enable_twitter = request.form.get('chkTW') == 'on'
    enable_instagram = request.form.get('chkIG') == 'on'
    enable_posthaven = request.form.get('chkPH') == 'on'
    enable_bluesky = request.form.get('chkBS') == 'on'
    enable_mastodon = request.form.get('chkMS') == 'on'
   
    # Process files and send email
    try:
        success_messages = []
        error_messages = []
        if enable_twitter:
            try:
                if textOnly: processed_files = []
                twitter.upload_to_twitter(processed_files, processed_alt_texts, text_mastodon)
                logger.debug('Posting to Twitter completed')
                success_messages.append('Twitter')
            except Exception as e:
                logger.error('Failed to post to Twitter. Error: %s', e)
                error_messages.append('Twitter')
                
        if enable_instagram: 
            try:
                logger.debug('Image locations: %s', image_locations)
                instagram.postInstagramCarousel(image_locations, text)
                logger.debug('Posting to Instagram completed')
                success_messages.append('Instagram')
            except Exception as e:
                logger.error('Failed to post to Instagram. Error: %s', e)
                error_messages.append('Instagram')
        if enable_posthaven:
            try:
                logger.debug('Sending email: %s', ', '.join(filename for filename, _ in processed_files))
                posthaven.send_email_with_attachments(subject, text, processed_files, processed_alt_texts)
                logger.debug('Sending email completed')
                success_messages.append('Posthaven')
            except Exception as e:
                logger.error('Failed to send email. Error: %s', e)
                error_messages.append('Posthaven')
        if enable_mastodon:
            try:
                logger.debug('Posting to Mastodon: %s', ', '.join(filename for filename, _ in processed_files))
                masto.post_to_mastodon(subject, text_mastodon, processed_files, processed_alt_texts)
                logger.debug('Posting to Mastodon completed')
                success_messages.append('Mastodon')
            except Exception as e:
                logger.error('Failed to post to Mastodon. Error: %s', e)
                error_messages.append('Mastodon')
        if enable_bluesky:
            try:
                logger.debug('Posting to Bluesky: %s', ', '.join(filename for filename, _ in processed_files))
                bluesky.post_to_bluesky(text_mastodon, processed_files, processed_alt_texts)
                logger.debug('Posting to Bluesky completed')
                success_messages.append('Bluesky')
            except Exception as e:
                logger.error('Failed to post to Bluesky. Error: %s', e)
                error_messages.append('Bluesky')
        helpers.delete_media_files_in_directory('.')
        helpers.delete_media_files_in_directory('temp')
        
        success_message = ''
        if success_messages:
            success_message = f'Successfully posted to: {", ".join(success_messages)}.'

        error_message = ''
        if error_messages:
            error_message = f'Failed to post to: {", ".join(error_messages)}. Error: {e}'

        if success_message and error_message:
            flash(f'{success_message} {error_message}')
        elif success_message:
            flash(success_message)
        elif error_message:
            flash(error_message)
    except Exception as e:
        error_message = f'Failed to execute functions. Error: {e}'
        line_number = inspect.currentframe().f_lineno
        logger.error(f'{error_message} (Line: {line_number})')
        flash(error_message)

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