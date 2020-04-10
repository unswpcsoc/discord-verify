import boto3
from botocore.exceptions import ClientError
from discord.ext import commands

from botcore.config import config

class MailError(Exception):
    pass

class Mail(commands.Cog):
    CHARSET = "UTF-8"

    def __init__(self):
        self.client = None
        self._connect()

    def send_email(self, recipient, subject, body_text):
        """
        Send a plaintext email via Amazon SES.

        Args:
            recipient: Email address of the intended recipient.
            subject: Subject line of the email.
            body_text: Body text of the email. Will be treated as plaintext.

        Raises:
            MailError: If email fails to send.
        """
        
        try:
            response = self.client.send_email(
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Body": {
                        "Text": {
                            "Charset": self.CHARSET,
                            "Data": body_text
                        }
                    },
                    "Subject": {
                        "Charset": self.CHARSET,
                        "Data": subject
                    }
                },
                Source=config["email-address"]
            )
            print(f"Email {response['MessageId']} sent to {recipient}")
        except ClientError:
            raise MailError("Email could not be sent!")

    def _connect(self):
        """
        Connect to Amazon SES. Required for all other methods to function.
        """

        self.client = boto3.client(
            'ses',
            region_name=config["aws-region"],
            aws_access_key_id=config["aws-access-key-id"],
            aws_secret_access_key=config["aws-secret-access-key"]
        )
        print("Connected to Amazon SES")
