# Social-cross-post

Cross-post to Bluesky, Mastodon, Posthaven, Instagram, Facebook and, ugh, Twitter in one fell swoop!

*[installation guide is a work in progress!!!]*

# How to Install "social-cross-post" on a Brand New Ubuntu Server Using nginx and Flask

## Step 1: Set Up the Ubuntu Server

Start by ensuring your system is up to date:

```sh
sudo apt update
sudo apt upgrade
```

## Step 2: Install Required Packages

Install Python, pip, virtualenv, nginx, and other necessary packages:

```sh
sudo apt install python3 python3-pip python3-venv nginx git
```

## Step 3: Clone the Repository

Clone the "social-cross-post" repository from GitHub to your server:

```sh
git clone https://github.com/GanWeaving/social-cross-post.git
cd social-cross-post
```
## Step 4: Set Up Virtual Environment

Create a virtual environment and activate it:

```sh
python3 -m venv venv
source venv/bin/activate
```
## Step 5: Install Python Libraries

Create a `requirements.txt` file with the following content:
```
pytz
Pillow
Flask
Flask-Session
Flask-APScheduler
Flask-SQLAlchemy
atproto
requests
Mastodon.py
tweepy
requests-oauthlib
```
Then execute this command:
```sh
pip install -r requirements.txt
```

## Step 6: Configure the Application

Make sure that your Flask application (`app.py`) is properly configured. You might need to set environment variables, configure databases, etc.

## Step 7: Start the Application with Gunicorn

Use Gunicorn as the WSGI server to serve the Flask app:

```sh
gunicorn -w 4 app:app
```

## Step 8: Configure nginx

Create a configuration file for your site in the `/etc/nginx/sites-available/` directory and create a symbolic link to it in the `/etc/nginx/sites-enabled/` directory.

Here is an example configuration file (replace `yourdomain.com` with your domain):

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```
Enable the configuration and restart nginx:
```
sudo ln -s /etc/nginx/sites-available/your-config /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```
## Step 9: Secure Your Site with Let's Encrypt (optional)

If you want to secure your site with HTTPS, you can use Certbot to obtain a free SSL certificate from Let's Encrypt:

```sh
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```
Follow the prompts to configure Certbot.
## Step 10: Access the Application

Now, you should be able to access your web application by visiting your domain in a web browser.




























