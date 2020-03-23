from enum import Enum
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
        self.states = self.fetch_unverified()

    @property
    def guild(self):
        return self.bot.get_guild(config["server-id"])

    class VerifyState():
        def __init__(self):
            self.full_name = None
            self.zid = None
            self.email = None
            self.email_verified = False

    def fetch_unverified(self):
        states = {}
        member_docs = self.db.collection("users").where("verified", "==", False).stream()
        for member_doc in member_docs:
            states[member_doc.id] = self.VerifyState()
            member_info = member_doc.to_dict()
            states[member_doc.id].full_name = member_info["full_name"]
            states[member_doc.id].zid = member_info["zid"]
            states[member_doc.id].email = member_info["email"]
            states[member_doc.id].verified = member_info["verified"]
        return states

    @commands.command(name="verify")
    @botcore.perms.in_allowed_channel(error=True)
    @botcore.perms.is_unverified_user(error=True)
    async def cmd_verify(self, ctx):
        await self.verify_begin(ctx.author)

    @commands.command(name="execverify")
    @botcore.perms.in_admin_channel(error=True)
    @botcore.perms.is_admin_user(error=True)
    async def cmd_exec_verify(self, ctx, member_id):
        await self.exec_verify(self.guild.get_member(int(member_id)))

    @commands.command(name="restart")
    @botcore.perms.in_dm_channel()
    @botcore.perms.is_guild_member(error=True)
    @botcore.perms.is_unverified_user()
    async def cmd_restart(self, ctx):
        await self.verify_restart(ctx.author)

    @commands.command(name="resend")
    @botcore.perms.in_dm_channel()
    @botcore.perms.is_guild_member(error=True)
    @botcore.perms.is_unverified_user()
    async def cmd_resend(self, ctx):
        member = self.guild.get_member(ctx.author.id)
        email = self.states[member.id].email
        await self.verify_email(member, email)

    @commands.Cog.listener()
    @botcore.perms.is_human()
    @botcore.perms.was_verified_user()
    async def on_member_join(self, member):
        pass

    def get_code(self, user):
        msg = bytes(str(user.id), "utf8")
        return hmac.new(self.secret, msg, "sha256").hexdigest()

    async def verify_begin(self, member):
        if member.id in self.states:
            await member.send("You are already undergoing the verification process. To restart, type `!restart`.")
            return

        self.states[member.id] = self.VerifyState()

        self.states[member.id].full_name = await request_input(self.bot, member, "What is your full name as it appears on your government-issued ID?\nYou can restart this verification process at any time by typing `!restart`.")

        if await request_yes_no(self.bot, member, "Are you a UNSW student?"):
            await self.verify_unsw(member)
        else:
            await self.verify_non_unsw(member)

    async def verify_unsw(self, member):
        zid = await request_input(self.bot, member, "What is your 7 digit student number, not including the 'z' at the start?")
        while True:
            if len(zid) != 7:
                zid = await request_input(self.bot, member, "Your response must be 7 characters long. Please try again.")
                continue
            try:
                zid = int(zid)
            except ValueError:
                zid = await request_input(self.bot, member, "Your response must be an integer. Please try again.")
            else:
                break
        self.states[member.id].zid = zid
        email = f"z{zid}@student.unsw.edu.au"
        self.states[member.id].email = email

        await self.verify_email(member, email)

    async def verify_non_unsw(self, member):
        email = await request_input(self.bot, member, "What is your email address?")
        self.states[member.id].email = email

        await self.verify_email(member, email)

    async def verify_email(self, member, email):
        async with member.typing():
            self.db.collection("users").document(str(member.id)).set({
                "full_name": self.states[member.id].full_name,
                "zid": self.states[member.id].zid,
                "email": email,
                "verified": False
            })
            expected_code = self.get_code(member)
            send_email(self.mail, email, "Discord Verification", f"Your code is {expected_code}")
        
        actual_code = await request_input(self.bot, member, "Please enter the code sent to your email (check your spam folder if you don't see it).\nYou can request another email by typing `!resend`.")
        while not hmac.compare_digest(actual_code, expected_code):
            actual_code = await request_input(self.bot, member, "That was not the correct code. Please try again.")
        self.states[member.id].email_verified = True

        if self.states[member.id].zid is None:
            await self.verify_id(member)
        else:
            await self.verify_complete(member)

    async def verify_id(self, member):
        attachment = (await request_attachments(self.bot, member, "Please send a message with a photo of your government-issued ID attached."))[0]

        async with member.typing():
            attached_file = await attachment.to_file()

            admin_channel = self.guild.get_channel(config["admin-channel"])
            await admin_channel.send(f"Received attachment from {member.mention}. Please verify that name on ID is `{self.states[member.id].full_name}`, then type `!execverify {member.id}`.", file=attached_file)

            await member.send("Your attachment has been forwarded to the admins. Please wait.")

    async def exec_verify(self, member):
        admin_channel = self.guild.get_channel(config["admin-channel"])
        if member.id not in self.states:
            await admin_channel.send("That user is not currently undergoing verification.")

        await self.verify_complete(member)

    async def exec_reject(self, member):
        admin_channel = self.guild.get_channel(config["admin-channel"])
        if member.id not in self.states:
            await admin_channel.send("That user is not currently undergoing verification.")
        
        pass

    async def verify_complete(self, member):
        async with member.typing():
            self.db.collection("users").document(str(member.id)).set({
                "full_name": self.states[member.id].full_name,
                "zid": self.states[member.id].zid,
                "email": self.states[member.id].email,
                "verified": True
            })

            await member.add_roles(self.guild.get_role(config["verified-role"]))

            del self.states[member.id]

            await member.send("You are now verified. Welcome to the server!")

        admin_channel = self.guild.get_channel(config["admin-channel"])
        await admin_channel.send(f"{member.mention} is now verified.")

    async def verify_restart(self, member):
        if member.id in self.states:
            await self.verify_begin(member)
