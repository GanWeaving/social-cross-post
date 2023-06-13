import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import logging
from config import (FASTMAIL_USERNAME, FASTMAIL_PASSWORD, EMAIL_RECIPIENTS)

logger = logging.getLogger()

def send_email_with_attachments(subject, body, processed_files, alt_texts):
    msg = MIMEMultipart()
    msg['From'] = FASTMAIL_USERNAME
    msg['To'] = ', '.join(EMAIL_RECIPIENTS)
    msg['Subject'] = subject

    # Append alt texts to the body
    if processed_files:  # Only process if there are files
        for idx, (filename, _) in enumerate(processed_files):
            alt_text = alt_texts[idx] if idx < len(alt_texts) else ""
            body += f'Image {idx+1}: <i><small>{alt_text if alt_text else "No alt text provided"}</small></i><br>'

            try:
                with open(filename, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f"attachment; filename= {idx+1}.jpg")
                    msg.attach(part)
            except Exception as e:
                # Log the error and raise it for further handling
                logger.exception(f"Unable to open one of the attachments. Error: {e}")
                #raise

    msg.attach(MIMEText(body, 'html'))  # Attach the body with alt text appended

    try:
        with smtplib.SMTP('smtp.fastmail.com', 587) as server:
            server.starttls()
            server.login(FASTMAIL_USERNAME, FASTMAIL_PASSWORD)
            server.sendmail(FASTMAIL_USERNAME, EMAIL_RECIPIENTS, msg.as_string())
    except Exception as e:
        logger.exception(f"Failed to send email. Error: {e}")
