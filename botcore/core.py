from discord.ext import commands

import botcore.perms

class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Bot running with command prefix '{self.bot.command_prefix}'")

    @commands.command(name="verifyexit")
    @botcore.perms.in_admin_channel(error=True)
    @botcore.perms.is_admin_user(error=True)
    async def cmd_verifyexit(self, ctx):
        await ctx.send("I am shutting down...")
        await self.bot.logout()
        print("Successfully logged out. Exiting...")
