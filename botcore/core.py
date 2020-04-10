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

"""Handle core functions of the bot."""

from discord.ext import commands

import botcore.perms

class Core(commands.Cog):
    """Handle core functions of the bot.

    Attributes:
        bot: Bot object that registered this cog.
    """
    def __init__(self, bot):
        """Initialise cog with given bot.

        Args:
            bot: Bot object that registered this cog.
        """
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Print message to console on bot startup."""
        print(f"Bot running with command prefix '{self.bot.command_prefix}'")

    @commands.group(name="iam")
    async def cmd_iam(self, ctx):
        """Register iam command group.

        Args:
            ctx: Context object associated with command invocation.
        """
        pass

    @cmd_iam.command(name="exit")
    @botcore.perms.in_admin_channel(error=True)
    @botcore.perms.is_admin_user(error=True)
    async def cmd_iam_exit(self, ctx):
        """Handle iam exit command.
        
        Gracefully log out and shut down the bot.

        Args:
            ctx: Context object associated with command invocation.
        """
        await ctx.send("I am shutting down...")
        await self.bot.logout()
        print("Successfully logged out. Exiting...")
