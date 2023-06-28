import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import logging
from config import (FASTMAIL_USERNAME, FASTMAIL_PASSWORD, EMAIL_RECIPIENTS)
from urllib.parse import urlparse

logger = logging.getLogger()

def send_email_with_attachments(subject, body, image_locations, alt_texts):
    msg = MIMEMultipart()
    msg['From'] = FASTMAIL_USERNAME
    msg['To'] = ', '.join(EMAIL_RECIPIENTS)
    msg['Subject'] = subject

    if image_locations:
        for idx, image_location in enumerate(image_locations):
            alt_text = alt_texts[idx] if idx < len(alt_texts) else ""
            body += f'Image {idx+1}: <i><small>{alt_text if alt_text else "No alt text provided"}</small></i><br>'

            try:
                # Parse the URL and get the path
                url_parts = urlparse(image_location)
                local_file_path = url_parts.path[1:]  # Remove the leading '/'

                # Open the image file from its location
                with open(local_file_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f"attachment; filename= {idx+1}.jpg")
                    msg.attach(part)

            except Exception as e:
                logger.exception(f"Unable to open one of the attachments. Error: {e}")

    msg.attach(MIMEText(body, 'html'))  # Attach the body with alt text appended

    try:
        with smtplib.SMTP('smtp.fastmail.com', 587) as server:
            server.starttls()
            server.login(FASTMAIL_USERNAME, FASTMAIL_PASSWORD)
            server.sendmail(FASTMAIL_USERNAME, EMAIL_RECIPIENTS, msg.as_string())
    except smtplib.SMTPResponseException as e:
        if e.smtp_code == 250:  # Email was sent successfully
            logger.info(f"Email sent successfully. Response: {e.smtp_error}")
        else:  # There was a problem
            logger.exception(f"Failed to send email. Error: {e.smtp_error}")
    except Exception as e:  # Some other exception occurred
        logger.exception(f"Failed to send email. Error: {e}")
