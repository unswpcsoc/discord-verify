from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from discord import DMChannel

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

# DM user with prompt.
# Return the text contents of their next message.
async def request_input(bot, user, prompt):
    await user.send(prompt)
    def check(_message):
        return _message.author.id == user.id \
            and isinstance(_message.channel, DMChannel)
    return (await bot.wait_for("message", check=check)).content

# DM user with prompt.
# Return the next list of attachments received.
async def request_attachments(bot, user, prompt):
    await user.send(prompt)
    def check(_message):
        return _message.author.id == user.id \
            and isinstance(_message.channel, DMChannel) \
            and len(_message.attachments) > 0
    return (await bot.wait_for("message", check=check)).attachments

# Send message as an email with title subject to recipient (an email address).
def send_email(mail_server, recipient, subject, message):
    msg = MIMEMultipart()
    msg["From"] = config["email-address"]
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(message, "plain"))
    mail_server.send_message(msg)
