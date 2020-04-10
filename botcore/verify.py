from enum import IntEnum
from functools import wraps
import hmac
from discord.ext import commands

import botcore.perms
from botcore.db import MemberKey, SecretID, MemberNotFound
from botcore.config import config
from botcore.utils import send_email

def _next_state(state):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, member, *args):
            await func(self, member, *args)
            patch = {MemberKey.STATE: state}
            self.db.update_member_data(member.id, patch)
            self.verifying[member.id].update(patch)
        return wrapper
    return decorator

class Verify(commands.Cog):
    class State(IntEnum):
        AWAIT_NAME = 0
        AWAIT_UNSW = 1
        AWAIT_ZID = 2
        AWAIT_EMAIL = 3
        AWAIT_CODE = 4
        AWAIT_ID = 5
        AWAIT_APPROVAL = 6

    def __init__(self, bot, mail_server):
        self.bot = bot
        self.mail = mail_server
        self._secret = None
        self.state_handler = [
            self.state_await_name,
            self.state_await_unsw,
            self.state_await_zid,
            self.state_await_email,
            self.state_await_code,
            self.state_await_id,
            self.state_await_approval
        ]
        self.verifying = self.db.get_unverified_members_data()

    @property
    def db(self):
        return self.bot.get_cog("Database")

    @property
    def secret(self):
        if self._secret is not None:
            return self._secret
        
        self._secret = self.db.get_secret(SecretID.VERIFY)
        return self._secret

    @property
    def guild(self):
        return self.bot.get_guild(config["server-id"])

    @commands.command(name="verify")
    @botcore.perms.in_allowed_channel(error=True)
    @botcore.perms.is_unverified_user(error=True)
    async def cmd_verify(self, ctx):
        await self.proc_begin(ctx.author)

    @commands.command(name="restart")
    @botcore.perms.in_dm_channel()
    @botcore.perms.is_guild_member(error=True)
    @botcore.perms.is_unverified_user()
    async def cmd_restart(self, ctx):
        await self.proc_restart(ctx.author)

    @commands.command(name="resend")
    @botcore.perms.in_dm_channel()
    @botcore.perms.is_guild_member(error=True)
    @botcore.perms.is_unverified_user()
    async def cmd_resend(self, ctx):
        await self.proc_resend_email(self.guild.get_member(ctx.author.id))

    @commands.command(name="execapprove")
    @botcore.perms.in_admin_channel(error=True)
    @botcore.perms.is_admin_user(error=True)
    async def cmd_exec_verify(self, ctx, member_id):
        await self.proc_exec_approve(self.guild.get_member(int(member_id)))

    @commands.command(name="execreject")
    @botcore.perms.in_admin_channel(error=True)
    @botcore.perms.is_admin_user(error=True)
    async def cmd_exec_reject(self, ctx, member_id, *reason):
        member = self.guild.get_member(int(member_id))
        reason = " ".join(reason)
        await self.proc_exec_reject(member, reason)

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
            state = self.verifying[member.id][MemberKey.STATE]
            await self.state_handler[state](member, message)

    def get_code(self, user):
        msg = bytes(str(user.id), "utf8")
        return hmac.new(self.secret, msg, "sha256").hexdigest()

    async def proc_begin(self, member):
        if member.id in self.verifying:
            await member.send("You are already undergoing the verification "
                "process. To restart, type `!restart`.")
            return
        
        try:
            if self.db.get_member_data(member.id)[MemberKey.ID_VER]:
                await self.proc_grant_rank(member)
                return
        except MemberNotFound:
            pass

        default_data = {
            MemberKey.STATE: None,
            MemberKey.NAME: None,
            MemberKey.ZID: None,
            "email": None,
            MemberKey.EMAIL_VER: False,
            MemberKey.ID_VER: False
        }
        self.verifying[member.id] = default_data
        self.db.set_member_data(member.id, default_data)

        await self.proc_request_name(member)

    async def proc_restart(self, user):
        if user.id not in self.verifying:
            await user.send("You are not currently being verified.")
            return

        del self.verifying[user.id]
        await self.proc_begin(user)

    @_next_state(State.AWAIT_NAME)
    async def proc_request_name(self, member):
        await member.send("What is your full name as it appears on your "
            "government-issued ID?\n"
            "You can restart this verification process at any time "
            "by typing `!restart`.")

    async def state_await_name(self, member, message):
        full_name = message.content
        self.db.update_member_data(member.id, {MemberKey.NAME: full_name})
        self.verifying[member.id][MemberKey.NAME] = full_name
        await self.proc_request_unsw(member)

    @_next_state(State.AWAIT_UNSW)
    async def proc_request_unsw(self, member):
        await member.send("Are you a UNSW student? Please type `y` or `n`.")

    async def state_await_unsw(self, member, message):
        ans = message.content
        if ans == "y":
            await self.proc_request_zid(member)
        elif ans == "n":
            await self.proc_request_email(member)
        else:
            await member.send("Please type `y` or `n`.")

    @_next_state(State.AWAIT_ZID)
    async def proc_request_zid(self, member):
        await member.send("What is your 7 digit student number, "
            "not including the 'z' at the start?")
    
    async def state_await_zid(self, member, message):
        zid = message.content
        if len(zid) != 7:
            await member.send("Your response must be 7 characters long. "
                "Please try again.")
            return
        try:
            zid = int(zid)
        except ValueError:
            await member.send("Your response must be an integer. "
                "Please try again.")
        email = f"z{zid}@student.unsw.edu.au"

        async with member.typing():
            patch = {MemberKey.ZID: zid, "email": email}
            self.db.update_member_data(member.id, patch)
            self.verifying[member.id].update(patch)

            await self.proc_send_email(member)

    @_next_state(State.AWAIT_EMAIL)
    async def proc_request_email(self, member):
        await member.send("What is your email address?")

    async def state_await_email(self, member, message):
        email = message.content

        async with member.typing():
            patch = {"email": email}
            self.db.update_member_data(member.id, patch)
            self.verifying[member.id].update(patch)

            await self.proc_send_email(member)

    @_next_state(State.AWAIT_CODE)
    async def proc_send_email(self, member):
        email = self.verifying[member.id]["email"]
        code = self.get_code(member)
        send_email(self.mail, email, "Discord Verification", 
            f"Your code is {code}")
        await member.send("Please enter the code sent to your email "
            "(check your spam folder if you don't see it).\n"
            "You can request another email by typing `!resend`.")

    async def state_await_code(self, member, message):
        async with member.typing():
            received_code = message.content
            expected_code = self.get_code(member)
            if not hmac.compare_digest(received_code, expected_code):
                await member.send("That was not the correct code. "
                    "Please try again.\n"
                    "You can request another email by typing `!resend`.")
                return

            patch = {MemberKey.EMAIL_VER: True}
            self.db.update_member_data(member.id, patch)
            self.verifying[member.id].update(patch)
            
            if self.verifying[member.id][MemberKey.ZID] is None:
                await self.proc_request_id(member)
            else:
                await self.proc_grant_rank(member)

    async def proc_resend_email(self, member):
        if member.id in self.verifying \
            and self.verifying[member.id][MemberKey.STATE] \
            == self.State.AWAIT_CODE:
            await self.proc_send_email(member)

    @_next_state(State.AWAIT_ID)
    async def proc_request_id(self, member):
        await member.send("Please send a message with a "
            "photo of your government-issued ID attached.")

    async def state_await_id(self, member, message):
        attachments = message.attachments
        if len(attachments) == 0:
            await member.send("No attachments received. Please try again.")
            return
        
        async with member.typing():
            await self.proc_send_id_admins(member, attachments)

    @_next_state(State.AWAIT_APPROVAL)
    async def proc_send_id_admins(self, member, attachments):
        first_file = await attachments[0].to_file()
        admin_channel = self.guild.get_channel(config["admin-channel"])
        full_name = self.verifying[member.id][MemberKey.NAME]
        await admin_channel.send(f"Received attachment from {member.mention}. "
            f"Please verify that name on ID is `{full_name}`, "
            f"then type `!execapprove {member.id}` "
            f"or `!execreject {member.id} reason`.", file=first_file)

        await member.send("Your attachment has been forwarded to the admins. "
            "Please wait.")

    async def state_await_approval(self, member, message):
        pass

    async def proc_exec_approve(self, member):
        admin_channel = self.guild.get_channel(config["admin-channel"])
        if member.id not in self.verifying:
            await admin_channel.send("That user is not currently "
                "undergoing verification.")
            return

        if self.verifying[member.id][MemberKey.STATE] \
            != self.State.AWAIT_APPROVAL:
            await admin_channel.send("That user is still "
                "undergoing verification.")
            return

        await self.proc_grant_rank(member)

    async def proc_exec_reject(self, member, reason):
        admin_channel = self.guild.get_channel(config["admin-channel"])
        if member.id not in self.verifying:
            await admin_channel.send("That user is not currently "
                "undergoing verification.")
            return

        if self.verifying[member.id][MemberKey.STATE] \
            != self.State.AWAIT_APPROVAL:
            await admin_channel.send("That user is still "
                "undergoing verification.")
            return
        
        self.db.delete_member_data(member.id, must_exist=False)
        del self.verifying[member.id]

        await member.send("Your verification request has been denied "
            f"for the following reason(s): `{reason}`.\n"
            "You can start a new request by typing `!verify` in the "
            "verification channel.")

        admin_channel = self.guild.get_channel(config["admin-channel"])
        await admin_channel.send("Rejected verification request from "
            f"{member.mention}.")

    async def proc_grant_rank(self, member):
        self.db.update_member_data(member.id, {MemberKey.ID_VER: True})
        await member.add_roles(self.guild.get_role(config["verified-role"]))
        if member.id in self.verifying:
            del self.verifying[member.id]
        await member.send("You are now verified. Welcome to the server!")

        admin_channel = self.guild.get_channel(config["admin-channel"])
        await admin_channel.send(f"{member.mention} is now verified.")
