from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from botcore.config import config

# DM user with prompt and yes/no reactions.
# Return True if user reacts yes, False if user reacts no.
async def request_yes_no(bot, user, prompt):
    message = await user.send(prompt)
    await message.add_reaction("✅")
    await message.add_reaction("❌")

    def check(_reaction, _user):
        return _reaction.message.id == message.id and _user.id == user.id \
            and str(_reaction.emoji) in ["✅", "❌"]
    reaction = (await bot.wait_for("reaction_add", check=check))[0]
    return str(reaction.emoji) == "✅"

# Send message as an email with title subject to recipient (an email address).
def send_email(mail_server, recipient, subject, message):
    msg = MIMEMultipart()
    msg["From"] = config["email-address"]
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))
    mail_server.send_message(msg)
