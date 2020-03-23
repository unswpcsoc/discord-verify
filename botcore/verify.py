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
    STATE_AWAIT_NAME, STATE_AWAIT_UNSW, STATE_AWAIT_ZID, STATE_AWAIT_EMAIL, \
        STATE_AWAIT_CODE, STATE_AWAIT_ID, STATE_AWAIT_APPROVAL = range(7)

    def __init__(self, bot, secret, db, mail_server):
        self.bot = bot
        self.secret = secret
        self.db = db
        self.mail = mail_server
        self.state_handler = [
            self.verify_state_await_name,
            self.verify_state_await_unsw,
            self.verify_state_await_zid,
            self.verify_state_await_email,
            self.verify_state_await_code,
            self.verify_state_await_id,
            self.verify_state_await_approval
        ]
        self.verifying = self.fetch_verifying()

    @property
    def guild(self):
        return self.bot.get_guild(config["server-id"])

    class VerifyingMember():
        def __init__(self):
            self.state = None
            self.full_name = None
            self.zid = None
            self.email = None
            self.email_verified = False

    def fetch_verifying(self):
        verifying = {}
        member_docs = self.db.collection("members").where("id_verified", "==", False).stream()
        for member_doc in member_docs:
            member_info = member_doc.to_dict()
            verifying[member_doc.id] = self.VerifyingMember()
            verifying[member_doc.id].state = member_info["_state"]
            verifying[member_doc.id].full_name = member_info["full_name"]
            verifying[member_doc.id].zid = member_info["zid"]
            verifying[member_doc.id].email = member_info["email"]
            verifying[member_doc.id].email_verified = member_info["email_verified"]
        return verifying

    @commands.command(name="verify")
    @botcore.perms.in_allowed_channel(error=True)
    @botcore.perms.is_unverified_user(error=True)
    async def cmd_verify(self, ctx):
        await self.verify_proc_begin(ctx.author)

    @commands.command(name="execapprove")
    @botcore.perms.in_admin_channel(error=True)
    @botcore.perms.is_admin_user(error=True)
    async def cmd_exec_verify(self, ctx, member_id):
        await self.verify_proc_exec_approve(self.guild.get_member(int(member_id)))

    @commands.command(name="restart")
    @botcore.perms.in_dm_channel()
    @botcore.perms.is_guild_member(error=True)
    @botcore.perms.is_unverified_user()
    async def cmd_restart(self, ctx):
        await self.verify_proc_restart(ctx.author)

    @commands.command(name="resend")
    @botcore.perms.in_dm_channel()
    @botcore.perms.is_guild_member(error=True)
    @botcore.perms.is_unverified_user()
    async def cmd_resend(self, ctx):
        await self.verify_proc_resend_email(self.guild.get_member(ctx.author.id))

    @commands.Cog.listener()
    @botcore.perms.is_human()
    @botcore.perms.was_verified_user()
    async def on_member_join(self, member):
        pass

    @commands.Cog.listener()
    @botcore.perms.in_dm_channel()
    @botcore.perms.is_human()
    @botcore.perms.is_not_command()
    @botcore.perms.is_guild_member()
    @botcore.perms.is_unverified_user()
    async def on_message(self, message):
        member = self.guild.get_member(message.author.id)
        if member.id in self.verifying:
            await self.state_handler[self.verifying[member.id].state](member, message)

    def get_code(self, user):
        msg = bytes(str(user.id), "utf8")
        return hmac.new(self.secret, msg, "sha256").hexdigest()

    async def verify_proc_begin(self, member):
        if member.id in self.verifying:
            await member.send("You are already undergoing the verification process. To restart, type `!restart`.")
        
        self.verifying[member.id] = self.VerifyingMember()
        self.verifying[member.id].full_name = None
        self.verifying[member.id].zid = None
        self.verifying[member.id].email = None
        self.verifying[member.id].email_verified = None
        self.db.collection("members").document(str(member.id)).set({
            "_state": None,
            "full_name": None,
            "zid": None,
            "email": None,
            "email_verified": False,
            "id_verified": False
        })

        await self.verify_proc_request_name(member)

    async def verify_proc_restart(self, user):
        del self.verifying[user.id]
        self.verify_proc_begin(user)

    async def verify_proc_request_name(self, member):
        await member.send("What is your full name as it appears on your government-issued ID?\nYou can restart this verification process at any time by typing `!restart`.")
        self.verifying[member.id].state = self.STATE_AWAIT_NAME

    async def verify_state_await_name(self, member, message):
        full_name = message.content
        self.db.collection("members").document(str(member.id)).update({"full_name": full_name})
        self.verifying[member.id].full_name = full_name
        await self.verify_proc_request_unsw(member)

    async def verify_proc_request_unsw(self, member):
        await member.send("Are you a UNSW student? Please type 'y' or 'n'.")
        self.verifying[member.id].state = self.STATE_AWAIT_UNSW

    async def verify_state_await_unsw(self, member, message):
        ans = message.content
        if ans == "y":
            await self.verify_proc_request_zid(member)
        elif ans == "n":
            await self.verify_proc_request_email(member)
        else:
            await member.send("Please type 'y' or 'n'.")

    async def verify_proc_request_zid(self, member):
        await member.send("What is your 7 digit student number, not including the 'z' at the start?")
        self.verifying[member.id].state = self.STATE_AWAIT_ZID
    
    async def verify_state_await_zid(self, member, message):
        zid = message.content
        if len(zid) != 7:
            await member.send("Your response must be 7 characters long. Please try again.")
            return
        try:
            zid = int(zid)
        except ValueError:
            await member.send("Your response must be an integer. Please try again.")
        email = f"z{zid}@student.unsw.edu.au"

        async with member.typing():
            self.db.collection("members").document(str(member.id)).update({
                "zid": zid,
                "email": email
            })
            self.verifying[member.id].zid = zid
            self.verifying[member.id].email = email

            await self.verify_proc_send_email(member)

    async def verify_proc_request_email(self, member):
        await member.send("What is your email address?")
        self.verifying[member.id].state = self.STATE_AWAIT_EMAIL

    async def verify_state_await_email(self, member, message):
        email = message.content

        async with member.typing():
            self.db.collection("members").document(str(member.id)).update({"email": email})
            self.verifying[member.id].email = email

            await self.verify_proc_send_email(member)

    async def verify_proc_send_email(self, member):
        email = self.verifying[member.id].email
        code = self.get_code(member)
        send_email(self.mail, email, "Discord Verification", f"Your code is {code}")
        await member.send("Please enter the code sent to your email (check your spam folder if you don't see it).\nYou can request another email by typing `!resend`.")
        self.verifying[member.id].state = self.STATE_AWAIT_CODE

    async def verify_state_await_code(self, member, message):
        async with member.typing():
            received_code = message.content
            expected_code = self.get_code(member)
            if not hmac.compare_digest(received_code, expected_code):
                await member.send("That was not the correct code. Please try again.\nYou can request another email by typing `!resend`.")
                return

            self.db.collection("members").document(str(member.id)).update({"email_verified": True})
            self.verifying[member.id].email_verified = True
            
            if self.verifying[member.id].zid is None:
                await self.verify_proc_request_id(member)
            else:
                await self.verify_proc_grant_rank(member)

    async def verify_proc_resend_email(self, member):
        if member.id in self.verifying and self.verifying[member.id].state == self.STATE_AWAIT_CODE:
            await self.verify_proc_send_email(member)

    async def verify_proc_request_id(self, member):
        await member.send("Please send a message with a photo of your government-issued ID attached.")
        self.verifying[member.id].state = self.STATE_AWAIT_ID

    async def verify_state_await_id(self, member, message):
        attachments = message.attachments
        if len(attachments) == 0:
            await member.send("No attachments received. Please try again.")
            return
        
        async with member.typing():
            await self.verify_proc_send_id_admins(member, attachments)

    async def verify_proc_send_id_admins(self, member, attachments):
        first_file = await attachments[0].to_file()
        admin_channel = self.guild.get_channel(config["admin-channel"])
        await admin_channel.send(f"Received attachment from {member.mention}. Please verify that name on ID is `{self.verifying[member.id].full_name}`, then type `!execapprove {member.id}` or `!execreject {member.id}`.", file=first_file)

        await member.send("Your attachment has been forwarded to the admins. Please wait.")

        self.verifying[member.id].state = self.STATE_AWAIT_APPROVAL

    async def verify_state_await_approval(self, member, message):
        pass

    async def verify_proc_exec_approve(self, member):
        admin_channel = self.guild.get_channel(config["admin-channel"])
        if member.id not in self.verifying:
            await admin_channel.send("That user is not currently undergoing verification.")

        if self.verifying[member.id].state != self.STATE_AWAIT_APPROVAL:
            await admin_channel.send("That user is still undergoing verification.")

        self.verifying[member.id].task = await self.verify_proc_grant_rank(member)

    async def verify_proc_exec_reject(self, member):
        admin_channel = self.guild.get_channel(config["admin-channel"])
        if member.id not in self.verifying:
            await admin_channel.send("That user is not currently undergoing verification.")

        # TODO: Implement this.

    async def verify_proc_grant_rank(self, member):
        self.db.collection("members").document(str(member.id)).update({"id_verified": True})
        await member.add_roles(self.guild.get_role(config["verified-role"]))
        del self.verifying[member.id]
        await member.send("You are now verified. Welcome to the server!")

        admin_channel = self.guild.get_channel(config["admin-channel"])
        await admin_channel.send(f"{member.mention} is now verified.")
