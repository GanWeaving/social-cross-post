# Python Standard Library
import os
import time
import inspect
import urllib.parse
from datetime import datetime

# Third-Party Libraries
import pytz
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_session import Session  # if you're using flask-session
from flask_apscheduler import APScheduler
from flask_sqlalchemy import SQLAlchemy
from flask import g
from sqlalchemy import inspect
#from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
#from apscheduler.triggers.date import DateTrigger

# Your Applications/Library specific modules
import helpers
from config import Config, MYPASSWORD
from models import ScheduledPosts
from extensions import db
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize db with app
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        table_exists = inspector.has_table(ScheduledPosts.__tablename__)
        if table_exists:
            print("ScheduledPosts table exists in the database.")
        else:
            print("ScheduledPosts table does not exist in the database.")

    return app

app = create_app()

Session(app)

# Setup logging
logger, speed_logger = helpers.configure_logging()

# Scheduler object to allow scheduling of tasks
scheduler = APScheduler()
scheduler.init_app(app)
logger.debug('Scheduler initialized')
scheduler.start()
logger.debug('Scheduler started')

@app.errorhandler(502)
def handle_bad_gateway_error(e):
    logger.error('Bad Gateway error: %s', str(e))
    logger.error('Request data: %s', request.data)
    return 'Bad Gateway', 502

@app.route('/')
def index():
    version = app.config['VERSION']
    logger.info('Index page loaded')
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', version=version)

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

    timezone = pytz.timezone('Europe/Berlin')  # Replace 'Your_Timezone' with your desired timezone

    start_time = time.time()

    scheduled_time = request.form.get('scheduled_time')
    if scheduled_time:
        scheduled_time = datetime.strptime(scheduled_time, '%Y-%m-%dT%H:%M')
        scheduled_time = timezone.localize(scheduled_time)
        logger.info('Scheduled Time: %s', scheduled_time)  # Log message
    else:
        scheduled_time = None

    if start_time is None:
        start_time = time.time()
   
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
        logger.info('sorted file pairs: %s', [pair[0].filename for pair in file_alt_text_pairs])

        # Unzip the list of tuples back into files and alt_texts using list comprehensions
        files, alt_texts = [list(t) for t in zip(*file_alt_text_pairs)]

        # Error handling for file upload limit
        if len(files) > 4:
            flash('Error: Maximum of 4 files are allowed.')
            return redirect(url_for('index'))

        # Process files and store resized images
        processed_files, processed_alt_texts, image_locations = process_files(files, alt_texts, scheduled_time) # Get image_locations
        logger.debug('Files after processing: %s', ', '.join(filename for filename, _ in processed_files))
    else:
        processed_files = []
        processed_alt_texts = []
        textOnly = True

    # Create the email subject
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
    enable_facebook = request.form.get('chkFB') == 'on'

    # Create post data dictionary to pass into the scheduled function
    post_data = {
        "text": text,
        "text_html": text_html,
        "text_mastodon": text_mastodon,
        "hashtag": hashtag,
        "hashtag_text": hashtag_text,
        "subject": subject,
        "enable_twitter": enable_twitter,
        "enable_instagram": enable_instagram,
        "enable_posthaven": enable_posthaven,
        "enable_bluesky": enable_bluesky,
        "enable_mastodon": enable_mastodon,
        "enable_facebook": enable_facebook,
        "processed_files": processed_files,
        "processed_alt_texts": processed_alt_texts,
        "image_locations": image_locations,
        "scheduled_time": scheduled_time,
        "textOnly": textOnly
    }

    if scheduled_time:
        # Convert string time to datetime object
        try:
            #scheduled_time = datetime.strptime(scheduled_time, '%Y-%m-%dT%H:%M:%S%z')  # Notice the added :%S%z
            logger.info('Scheduled Time: %s', scheduled_time)  # Log message
        except ValueError:
            logger.info('Error: Scheduled Time format is incorrect.')
            return redirect(url_for('index'))

        # Convert local time to UTC
        utc_dt = scheduled_time.astimezone(pytz.utc)

        # Schedule post for later
        with app.app_context():
            post = helpers.save_post_to_database(post_data)  # Get the post object
            if post is None:
                # If post is None, there was an error saving it to the database, so we skip scheduling the post
                logger.error('Post could not be saved to the database, skipping scheduling.')
                return redirect(url_for('index'))
            logger.debug('Post saved to the database')

            job_id = str(post.id)
            scheduler.add_job(id=job_id, func='helpers:send_scheduled_post', args=[app, post.id], trigger='date', run_date=utc_dt)
            logger.debug('Scheduled post added to the job queue')

        logger.debug('Your post has been scheduled.')
    else:
        # Post immediately
        helpers.send_post(post_data)

    end_time = time.time()
    speed_logger.info(f"OVERALL execution time: {end_time-start_time} seconds")

    return redirect(url_for('index'))

def process_files(files, alt_texts, scheduled_time):
    if not files or files[0].filename == '':
        return [], [], []

    processed_files = []
    processed_alt_texts = []
    image_locations = []
    temp_dir = os.path.join(app.root_path, 'static/temp')

    if scheduled_time:
        # Create a subfolder based on the scheduled time
        folder_name = scheduled_time.strftime("%Y%m%d_%H%M%S")
    else:
        # If it's not scheduled_time, use the current time as the folder name
        folder_name = datetime.now().strftime("%Y%m%d_%H%M%S")

    temp_dir = os.path.join(temp_dir, folder_name)
    os.makedirs(temp_dir, exist_ok=True)

    for (file, alt_text) in zip(files, alt_texts):
        try:
            image = Image.open(file).convert("RGB")
            filename = urllib.parse.quote(os.path.splitext(file.filename)[0]) + '.jpg'
            temp_file_path = os.path.join(temp_dir, filename)

            image.save(temp_file_path, 'JPEG', quality=90)
            logger.info('Saved processed image: %s', temp_file_path)

            #if scheduled_time:
            image_url = url_for('static', filename=f'temp/{folder_name}/{filename}', _external=True)
            #else:
            #    image_url = url_for('static', filename=f'temp/{filename}', _external=True)
            image_locations.append(image_url)
            logger.info('Appended image URL: %s', image_url)

            with open(temp_file_path, 'rb') as img_file:
                processed_files.append((temp_file_path, helpers.resize_image(img_file)))
            processed_alt_texts.append(alt_text)
            logger.info('Processed file: %s', temp_file_path)

        except Exception as e:
            logger.debug(f"Unable to process one of the attachments. Error: {e}")
            raise

    return processed_files, processed_alt_texts, image_locations



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)