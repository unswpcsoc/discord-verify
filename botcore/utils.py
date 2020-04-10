from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from botcore.config import config

def send_email(mail_server, recipient, subject, message):
    """
    Send message as an email with title subject to recipient.
    """
    
    msg = MIMEMultipart()
    msg["From"] = config["email-address"]
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))
    mail_server.send_message(msg)
