import discord
from discord.ext import commands

from botcore.config import config
from botcore.utils import request_yes_no, request_input

class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.users = {}

    class VerifyState():
        def __init__(self):
            self.unsw = None
            self.full_name = None
            self.zid = None
            self.email = None
            self.verified = None

    @commands.command(name="verify")
    async def cmd_verify(self, ctx):
        if ctx.message.channel.id not in config["allowed-channels"]:
            return

        await self.verify_begin(ctx.message.author)

    @commands.command(name="restart")
    async def cmd_restart(self, ctx):
        if not isinstance(ctx.message.channel, discord.DMChannel):
            return

        user = ctx.message.author
        if user.id in self.users:
            del self.users[user.id]
            await self.verify_begin(user)

    async def verify_begin(self, user):
        if user.id in self.users:
            await user.send("You are already undergoing the verification process. To restart, type `!restart`.")
            return
        self.users[user.id] = self.VerifyState()

        if await request_yes_no(self.bot, user, "Are you a UNSW student? You can restart this verification process at any time by typing `!restart`."):
            await self.verify_unsw(user)
        else:
            await self.verify_non_unsw(user)

    async def verify_unsw(self, user):
        self.users[user.id].unsw = True

        self.users[user.id].full_name = await request_input(self.bot, user, "What is your full name as it appears on your student ID?")

        zid = await request_input(self.bot, user, "What is your 7 digit student number, not including the 'z' at the start?")
        while True:
            if len(zid) != 7:
                zid = await request_input(self.bot, user, "Your response must be 7 characters long. Please try again.")
                continue
            try:
                zid = int(zid)
            except ValueError:
                zid = await request_input(self.bot, user, "Your response must be an integer. Please try again.")
            else:
                break
        self.users[user.id].zid = zid

        self.users[user.id].email = f"{zid}@student.unsw.edu.au"

    async def verify_non_unsw(self, user):
        self.users[user.id].unsw = False

        self.users[user.id].full_name = await request_input(self.bot, user, "What is your full name as it appears on your government-issued ID?")

        self.users[user.id].email = await request_input(self.bot, user, "What is your email address?")
