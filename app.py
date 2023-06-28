# Python Standard Library
import os
import time
import inspect
import urllib.parse
from datetime import datetime
import shutil

# Third-Party Libraries
import pytz
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_session import Session  # if you're using flask-session
from flask_apscheduler import APScheduler
from flask_sqlalchemy import SQLAlchemy
from flask import g
from sqlalchemy import inspect
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.date import DateTrigger

# Your Applications/Library specific modules
import helpers
import posthaven
import bluesky
import instagram
import masto
import twitter
import facebook
from config import Config, MYPASSWORD

app = Flask(__name__)
app.config.from_object(Config)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///posts.db'  # this is where the SQLite database file will be stored
app.config['SCHEDULER_JOBSTORES'] = {
    'default': SQLAlchemyJobStore(url='sqlite:///jobs.db')
}
app.config['SCHEDULER_API_ENABLED'] = True

db = SQLAlchemy(app)

class ScheduledPosts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    post_data = db.Column(db.PickleType, nullable=False)
    posted = db.Column(db.Boolean, default=False)  # New field 'posted' with default value False

with app.app_context():
    db.create_all()
    inspector = inspect(db.engine)
    table_exists = inspector.has_table(ScheduledPosts.__tablename__)
    if table_exists:
        print("ScheduledPosts table exists in the database.")
    else:
        print("ScheduledPosts table does not exist in the database.")
    

# Setup logging
logger, speed_logger = helpers.configure_logging()

Session(app)

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
        processed_files, processed_alt_texts, image_locations = process_files(files, alt_texts, scheduled_time)  # Get image_locations
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
            post = save_post_to_database(post_data)  # Get the post object
            if post is None:
                # If post is None, there was an error saving it to the database, so we skip scheduling the post
                logger.error('Post could not be saved to the database, skipping scheduling.')
                return redirect(url_for('index'))
            logger.debug('Post saved to the database')

            job_id = str(post.id)
            scheduler.add_job(id=job_id, func='app:send_scheduled_post', args=[post.id], trigger='date', run_date=utc_dt)
            logger.debug('Scheduled post added to the job queue')

        logger.debug('Your post has been scheduled.')
    else:
        # Post immediately
        send_post(post_data)

    end_time = time.time()
    speed_logger.info(f"OVERALL execution time: {end_time-start_time} seconds")

    return redirect(url_for('index'))

def send_scheduled_post(post_id):
    logger.debug('send_scheduled_post function triggered')

    with app.app_context():
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

            try:
                scheduled_folder = scheduled_time.strftime("%Y%m%d_%H%M%S")
                temp_dir = os.path.join(app.root_path, 'static/temp', scheduled_folder)
                helpers.delete_media_files_in_directory(temp_dir)
            except Exception as e:
                error_message = f'Failed to delete media files. Error: {e}'
                line_number = inspect.currentframe().f_lineno
                logger.error(f'{error_message} (Line: {line_number})')
        else:
            logger.debug(f"Post {post.id} is not yet due to be posted.")

def save_post_to_database(post_data):
    scheduled_time = post_data.get('scheduled_time')

    if scheduled_time:
        try:
            timezone = pytz.timezone('Europe/Berlin')
            utc_scheduled_time = scheduled_time.astimezone(pytz.utc)
        except Exception as e:
            logger.exception('Error occurred while converting scheduled time: %s', e)
            return

        # Remove processed_files from the post_data
        if 'processed_files' in post_data:
            del post_data['processed_files']

        post = ScheduledPosts(text=post_data.get('text'), scheduled_time=utc_scheduled_time, post_data=post_data)
        try:
            db.session.add(post)
            db.session.commit()
            logger.info('Post saved to the database.')
            flash('Post has been scheduled!')
        except Exception as e:
            db.session.rollback()
            logger.exception('Error occurred while saving post to the database: %s', e)
            return None

        return post
    else:
        logger.info('Scheduled time is not provided. Posting immediately.')

def send_post(post_data):

    # Add success_messages and error_messages to post_data
    post_data['success_messages'] = []
    post_data['error_messages'] = []

    try:

        start = None
        end = None
        
        if post_data['enable_twitter']:
            start = time.time()
            try:
                if post_data['textOnly']: post_data['processed_files'] = []
                twitter.upload_to_twitter(post_data['image_locations'], post_data['processed_alt_texts'], post_data['text_mastodon'])
                end = time.time()
                speed_logger.info(f"Twitter upload execution time: {end - start} seconds")
                logger.debug('Posting to Twitter completed')
                #flash('Successfully posted to Twitter')
                post_data['success_messages'].append('Twitter')
            except Exception as e:
                logger.error('Failed to post to Twitter. Error: %s', e)
                #flash(f'Failed to post to Twitter. Error: {e}')
                post_data['error_messages'].append('Twitter')

        if post_data['enable_mastodon']:
            start = time.time()
            try:
                logger.debug('Posting to Mastodon: %s', ', '.join(post_data['image_locations']))
                masto.post_to_mastodon(post_data['subject'], post_data['text_mastodon'], post_data['image_locations'], post_data['processed_alt_texts'])
                end = time.time()
                speed_logger.info(f"Mastodon post execution time: {end - start} seconds")
                logger.debug('Posting to Mastodon completed')
                #flash('Successfully posted to Mastodon')
                post_data['success_messages'].append('Mastodon')
            except Exception as e:
                logger.error('Failed to post to Mastodon. Error: %s', e)
                #flash(f'Failed to post to Mastodon. Error: {e}')
                post_data['error_messages'].append('Mastodon')

        if post_data['enable_bluesky']:
            start = time.time()
            try:
                bluesky.login_to_bluesky()
                logger.debug('Posting to Bluesky: %s images', len(post_data['image_locations']))
                bluesky.post_to_bluesky(post_data['text_mastodon'], post_data['image_locations'], post_data['processed_alt_texts'])
                end = time.time()
                speed_logger.info(f"Bluesky post execution time: {end - start} seconds")
                logger.debug('Posting to Bluesky completed')
                #flash('Successfully posted to Bluesky')
                post_data['success_messages'].append('Bluesky')
            except Exception as e:
                logger.error('Failed to post to Bluesky. Error: %s', e)
                post_data['error_messages'].append('Bluesky')
                #flash(f'Failed to post to Bluesky. Error: {e}')

        if post_data['enable_posthaven']:
            start = time.time()
            try:
                logger.debug('Sending email: %s', ', '.join(image_location for image_location in post_data['image_locations']))
                posthaven.send_email_with_attachments(post_data['subject'], post_data['text'], post_data['image_locations'], post_data['processed_alt_texts'])
                end = time.time()
                speed_logger.info(f"Posthaven email execution time: {end - start} seconds")
                logger.debug('Sending email completed')
                #flash('Successfully posted to Posthaven')
                post_data['success_messages'].append('Posthaven')
            except Exception as e:
                logger.error('Failed to send email. Error: %s', e)
                #flash(f'Failed to post to Posthaven. Error: {e}')
                post_data['error_messages'].append('Posthaven')

        if post_data['enable_facebook']:
            start = time.time()
            try:
                facebook.post_to_facebook(post_data['image_locations'], post_data['text_mastodon'], post_data['processed_alt_texts'])  # Include alt_texts as a parameter
                end = time.time()
                speed_logger.info(f"Facebook post execution time: {end - start} seconds")
                logger.debug('Posting to Facebook completed')
                #flash('Successfully posted to Facebook')
                post_data['success_messages'].append('Facebook')
            except Exception as e:
                logger.error('Failed to post to Facebook. Error: %s', e)
                #flash(f'Failed to post to Facebook. Error: {e}')
                post_data['error_messages'].append('Facebook')

        if post_data['enable_instagram']:
            start = time.time()
            try:
                instagram.postInstagramCarousel(post_data['image_locations'], post_data['text'])
                end = time.time()
                speed_logger.info(f"Instagram post execution time: {end - start} seconds")
                logger.debug('Posting to Instagram completed')
                #flash('Successfully posted to Instagram')
                post_data['success_messages'].append('Instagram')
            except Exception as e:
                logger.error('Failed to post to Instagram. Error: %s', e)
                #flash(f'Failed to post to Instagram! Error: {e}')
                post_data['error_messages'].append('Instagram')

        
        try:
            #helpers.delete_media_files_in_directory('.')
            helpers.delete_media_files_in_directory('static/temp')
            #delete_directory(directory)
        except Exception as e:
            error_message = f'Failed to delete media files. Error: {e}'
            line_number = inspect.currentframe().f_lineno
            logger.error(f'{error_message} (Line: {line_number})')
            #flash(error_message)
    
        # Refer to post_data dictionary to form success and error messages
        success_message = ''
        if post_data['success_messages']:
            success_message = f'Successfully posted to: {", ".join(post_data["success_messages"])}.'

        error_message = ''
        if post_data['error_messages']:
            error_message = f'Failed to post to: {", ".join(post_data["error_messages"])}.'

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

    except Exception as e:
        error_message = f'Failed to execute functions. Error: {e}'
        line_number = inspect.currentframe().f_lineno
        logger.error(f'{error_message} (Line: {line_number})')
        if post_data.get('scheduled_time'):
            flash(error_message)

def delete_directory(directory):
    try:
        shutil.rmtree(directory)
        logger.debug(f"Deleted directory: {directory}")
    except Exception as e:
        logger.error(f"Failed to delete directory {directory}. Error: {e}")

def process_files(files, alt_texts, scheduled_time):
    if not files or files[0].filename == '':
        return [], [], []

    processed_files = []
    processed_alt_texts = []
    image_locations = []
    temp_dir = os.path.join(app.root_path, 'static/temp')

    if scheduled_time:
        # Create a subfolder based on the scheduled time
        scheduled_folder = scheduled_time.strftime("%Y%m%d_%H%M%S")
        temp_dir = os.path.join(temp_dir, scheduled_folder)
        os.makedirs(temp_dir, exist_ok=True)

    for (file, alt_text) in zip(files, alt_texts):
        try:
            image = Image.open(file).convert("RGB")
            filename = urllib.parse.quote(os.path.splitext(file.filename)[0]) + '.jpg'
            if scheduled_time:
                temp_file_path = os.path.join(temp_dir, filename)
            else:
                temp_file_path = os.path.join(temp_dir, filename)

            image.save(temp_file_path, 'JPEG', quality=90)
            logger.info('Saved processed image: %s', temp_file_path)

            if scheduled_time:
                image_url = url_for('static', filename=f'temp/{scheduled_folder}/{filename}', _external=True)
            else:
                image_url = url_for('static', filename=f'temp/{filename}', _external=True)
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