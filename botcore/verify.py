import hmac
import discord
from discord.ext import commands

import botcore.perms
from botcore.config import config
from botcore.utils import (
    request_yes_no, request_input, send_email, request_attachments
)

class Verify(commands.Cog):
    def __init__(self, bot, secret, db, mail_server):
        self.bot = bot
        self.secret = secret
        self.db = db
        self.mail = mail_server
        self.users = {}

    class VerifyState():
        def __init__(self):
            self.full_name = None
            self.zid = None
            self.email = None

    @commands.command(name="verify")
    @botcore.perms.in_allowed_channel()
    @botcore.perms.is_unverified_user()
    async def cmd_verify(self, ctx):
        await self.verify_begin(ctx.author)

    @commands.command(name="execverify")
    @botcore.perms.in_admin_channel()
    @botcore.perms.is_admin_user()
    async def cmd_exec_verify(self, ctx, user_id):
        user_id = int(user_id)
        if user_id not in self.users:
            return

        admin_channel = ctx.guild.get_channel(config["admin-channel"])

        self.db.collection("users").document(str(user_id)).set({
            "full_name": self.users[user_id].full_name,
            "email": self.users[user_id].email
        })

        user = ctx.guild.get_member(user_id)

        await user.add_roles(ctx.guild.get_role(config["verified-role"]))
        await user.send("You are now verified. Welcome to the server!")

        await admin_channel.send(f"{user.mention} is now verified.")

        del self.users[user_id]

    @commands.command(name="restart")
    @commands.dm_only()
    async def cmd_restart(self, ctx):
        user = ctx.author
        if user.id in self.users:
            del self.users[user.id]
            await self.verify_begin(user)

    def get_code(self, user):
        msg = bytes(str(user.id), "utf8")
        return hmac.new(self.secret, msg, "sha256").hexdigest()

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
        full_name = await request_input(self.bot, user, "What is your full name as it appears on your student ID?")
        self.users[user.id].full_name = full_name

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

        email = f"z{zid}@student.unsw.edu.au"
        self.users[user.id].email = email

        expected_code = self.get_code(user)
        send_email(self.mail, email, "Discord Verification", f"Your code is {expected_code}")
        actual_code = await request_input(self.bot, user, "Please enter the code sent to your student email (check your spam folder if you don't see it).")
        while not hmac.compare_digest(actual_code, expected_code):
            actual_code = await request_input(self.bot, user, "That was not the correct code. Please try again.")

        self.db.collection("users").document(str(user.id)).set({
            "zid": zid,
            "full_name": full_name,
            "email": email
        })

        await user.add_roles(user.guild.get_role(config["verified-role"]))
        await user.send("You are now verified. Welcome to the server!")

        del self.users[user.id]

    async def verify_non_unsw(self, user):
        full_name = await request_input(self.bot, user, "What is your full name as it appears on your government-issued ID?")
        self.users[user.id].full_name = full_name

        email = await request_input(self.bot, user, "What is your email address?")
        self.users[user.id].email = email

        expected_code = self.get_code(user)
        send_email(self.mail, email, "Discord Verification", f"Your code is {expected_code}")
        actual_code = await request_input(self.bot, user, "Please enter the code sent to your email (check your spam folder if you don't see it).")
        while not hmac.compare_digest(actual_code, expected_code):
            actual_code = await request_input(self.bot, user, "That was not the correct code. Please try again.")

        attachment = (await request_attachments(self.bot, user, "Please send a message with a photo of your government-issued ID attached."))[0]
        attached_file = await attachment.to_file()

        admin_channel = user.guild.get_channel(config["admin-channel"])
        await admin_channel.send(f"Received attachment from {user.mention}. Please verify that name on ID is {full_name}, then type `!execverify {user.id}`.", file=attached_file)
