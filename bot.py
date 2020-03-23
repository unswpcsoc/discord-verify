#!/usr/bin/env python3

from discord.ext import commands

import botcore.perms
from botcore.config import config
from botcore.db import Database
from botcore.mail import Mail
from botcore.verify import Verify
from botcore.sign import Sign

if __name__ == "__main__":
    bot = commands.Bot(command_prefix=config["command-prefix"])

    @bot.event
    async def on_ready():
        print(f"Bot running with command prefix {bot.command_prefix}")

    @bot.command(name="exit")
    @botcore.perms.is_admin_user()
    async def cmd_exit(ctx):
        await ctx.send("I am shutting down...")
        await bot.logout()
        print("Successfully logged out. Exiting...")

    bot.add_cog(Database())
    bot.add_cog(Mail())
    bot.add_cog(Verify(bot))
    bot.add_cog(Sign(bot))

    bot.run(config["bot-token"])
