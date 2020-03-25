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
from inspect import getdoc

from iam.config import PREFIX
import iam.perms

def setup(bot):
    """Add Core cog to bot.

    Args:
        bot: Bot object to add cog to.
    """
    bot.add_cog(Core(bot))

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
        self.bot.remove_command("help")

    @commands.Cog.listener()
    async def on_ready(self):
        """Print message to console on bot startup."""
        print(f"Bot running with command prefix '{self.bot.command_prefix}'")

    @commands.command(
        name="help",
        help="Display this help dialogue.",
        usage=f"**{PREFIX}help**"
    )
    @iam.perms.in_admin_channel(error=True)
    @iam.perms.is_admin_user(error=True)
    async def cmd_help(self, ctx):
        """Handle help command.

        Display list of all commands, their usage and their subcommands.

        Args:
            ctx. Context object associated with command invocation.
        """
        out = ["__All commands:__"]
        for cmd in self.bot.commands:
            if cmd.hidden:
                continue
            help = [str(cmd.usage), cmd.help]
            if isinstance(cmd, commands.Group) \
                and len(cmd.commands) > 0:
                subs = ["__Subcommands__"]
                subs += [f"{PREFIX}{c.qualified_name}" for c in cmd.commands]
                help.append(" | ".join(subs))
            out.append("\n".join(help))
        await ctx.send("\n\n".join(out))

    @commands.command(
        name="exit",
        help="Gracefully log out and shut down the bot.",
        usage=f"**{PREFIX}exit**"
    )
    @iam.perms.in_admin_channel(error=True)
    @iam.perms.is_admin_user(error=True)
    async def cmd_exit(self, ctx):
        """Handle exit command.
        
        Gracefully log out and shut down the bot.

        Args:
            ctx: Context object associated with command invocation.
        """
        await ctx.send("I am shutting down...")
        await self.bot.logout()
        print("Successfully logged out. Exiting...")
