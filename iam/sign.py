"""Currently unimplemented."""

from nextcord.ext import commands


def setup(bot):
    """Add Sign cog to bot.

    Args:
        bot: Bot object to add cog to.
    """
    bot.add_cog(Sign(bot))


class Sign(commands.Cog):
    """Currently unimplemented."""

    def __init__(self, bot):
        self.bot = bot
