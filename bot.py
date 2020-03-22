#!/usr/bin/env python3

import firebase_admin
from firebase_admin import credentials, firestore
import secrets
import smtplib
import discord
from discord.ext import commands

import botcore.perms
from botcore.config import config
from botcore.verify import Verify
from botcore.sign import Sign

# Set up Firebase connection
cred = credentials.Certificate("config/firebase_credentials.json")
default_app = firebase_admin.initialize_app(cred)
db = firestore.client()
print("Logged in to Firebase")

# Get verification secret
try:
    secret = db.collection("secrets").document("verify").get().to_dict()["secret"]
except TypeError:
    print("Generating new verification secret...")
    secret = secrets.token_bytes(64)
    db.collection("secrets").document("verify").set({"secret": secret})
    print("Saved verification secret in Firebase")
else:
    print("Fetched verification secret from Firebase")

# Set up mail server
mail = smtplib.SMTP(host=config["smtp-server"], port=config["smtp-port"])
mail.starttls()
mail.login(config["email-address"], config["email-password"])
print("Logged in to mail server")

bot = commands.Bot(command_prefix=config["command-prefix"])

@bot.event
async def on_ready():
    print(f"Bot running with command prefix {bot.command_prefix}")

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(str(error))

@bot.command(name="exit")
@botcore.perms.is_admin_user()
async def cmd_exit(ctx):
    await ctx.send("I am shutting down...")
    mail.quit()
    await bot.logout()
    print("Successfully logged out. Exiting...")

bot.add_cog(Verify(bot, secret, db, mail))
bot.add_cog(Sign(bot))

bot.run(config["bot-token"])
