#!/usr/bin/env python3

import secrets
import smtplib
import discord
from discord.ext import commands

from botcore.config import config
from botcore.utils import admin_check
from botcore.verify import Verify
from botcore.sign import Sign

secret = secrets.token_bytes(64)

# Set up mail server
mail = smtplib.SMTP(host=config["smtp-server"], port=config["smtp-port"])
mail.starttls()
mail.login(config["email-address"], config["email-password"])
print("Logged in to mail server")

bot = commands.Bot(command_prefix=config["command-prefix"])

@bot.event
async def on_ready():
    print(f"Bot running with command prefix {bot.command_prefix}")

@bot.command(name="exit")
async def cmd_exit(ctx):
    if not await admin_check(ctx.channel, ctx.author):
        return

    await ctx.send("I am shutting down...")
    mail.quit()
    await bot.logout()
    print("Successfully logged out. Exiting...")

bot.add_cog(Verify(bot, secret, mail))
bot.add_cog(Sign(bot))

bot.run(config["bot-token"])
