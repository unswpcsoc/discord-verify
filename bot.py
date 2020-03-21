#!/usr/bin/env python3

import discord
from discord.ext import commands

from botcore.config import config
from botcore.utils import admin_check
from botcore.verify import Verify
from botcore.sign import Sign

bot = commands.Bot(command_prefix=config["command-prefix"])

@bot.event
async def on_ready():
    print(f"Bot running with command prefix {bot.command_prefix}")

@bot.command(name="exit")
async def cmd_exit(ctx):
    if not await admin_check(ctx.message.channel, ctx.message.author):
        return

    await ctx.send(f"I am shutting down...")
    await bot.logout()
    print(f"Successfully logged out. Exiting...")

bot.add_cog(Verify(bot))
bot.add_cog(Sign(bot))

bot.run(config["bot-token"])
