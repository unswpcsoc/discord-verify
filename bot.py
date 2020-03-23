#!/usr/bin/env python3

from discord.ext import commands

import botcore.perms
from botcore.config import config
from botcore.core import Core
from botcore.db import Database
from botcore.mail import Mail
from botcore.verify import Verify
from botcore.sign import Sign

if __name__ == "__main__":
    bot = commands.Bot(command_prefix=config["command-prefix"])

    bot.add_cog(Core(bot))
    bot.add_cog(Database())
    bot.add_cog(Mail())
    bot.add_cog(Verify(bot))
    bot.add_cog(Sign(bot))

    bot.run(config["bot-token"])
