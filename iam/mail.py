"""MIT License

Copyright (c) 2020 Computer Enthusiasts Society

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""Handle email functions."""

import boto3
from botocore.exceptions import ClientError
from discord.ext import commands

from iam.config import (
    EMAIL, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
)

def setup(bot):
    """Add Mail cog to bot.

    Args:
        bot: Bot object to add cog to.
    """
    bot.add_cog(Mail())

class MailError(Exception):
    """Email failed to send."""
    pass

class Mail(commands.Cog):
    """Handle email functions"""
    CHARSET = "UTF-8"
    """String representing encoding used for emails."""

    def __init__(self):
        """Init cog and connect to Amazon SES."""
        self.client = None
        self._connect()

    def send_email(self, recipient, subject, body_text):
        """Send plaintext email via Amazon SES.

        Args:
            recipient: String representing Email address of intended recipient.
            subject: String representing subject line of email.
            body_text: String representing body text of the email. Will be
                       treated as plaintext.

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
                Source=EMAIL
            )
            print(f"Email {response['MessageId']} sent to {recipient}")
        except ClientError:
            raise MailError("Email could not be sent!")

    def _connect(self):
        """Connect to Amazon SES.
        
        Required for all other methods to function.
        """
        self.client = boto3.client(
            'ses',
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
        print("Connected to Amazon SES")
