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

"""Handle automatic verification of server members."""

from enum import IntEnum
from functools import wraps
import hmac
from discord.ext import commands

import botcore.perms
from botcore.db import MemberKey, SecretID, MemberNotFound
from botcore.mail import MailError
from botcore.config import config

def _next_state(state):
    """Decorate function to trigger state change on completion.

    Used with the Verify class to implement a finite state machine.

    Args:
        state: The state to transition to once function completes execution.
    """
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
    """Handle automatic verification of server members.

    Verification process for each member implemented as a finite state machine.

    Attributes:
        State: Enum representing all possible states in the FSM.
        verifying: Dict of all members undergoing verification. Keys are member
                   Discord IDs and values are dicts containing state, name,
                   zID, email, email verified status and ID verified status.
                   Refer to botcore.db.MemberKey.
        bot: Bot object that registered this cog.
        guild: Guild object associated with bot, defined in config.
        db: Database cog associated with bot.
        mail: Mail cog associated with bot.
    """
    class State(IntEnum):
        """Enum representing all possible states in the FSM."""
        AWAIT_NAME = 0
        AWAIT_UNSW = 1
        AWAIT_ZID = 2
        AWAIT_EMAIL = 3
        AWAIT_CODE = 4
        AWAIT_ID = 5
        AWAIT_APPROVAL = 6

    def __init__(self, bot):
        """Init cog with given bot.
        
        Args:
            bot: Bot object that registered this cog.
        """
        self.bot = bot
        self.__secret_ = None
        self.__state_handler = [
            self.__state_await_name,
            self.__state_await_unsw,
            self.__state_await_zid,
            self.__state_await_email,
            self.__state_await_code,
            self.__state_await_id,
            self.__state_await_approval
        ]
        self.verifying = self.db.get_unverified_members_data()

    @property
    def guild(self):
        return self.bot.get_guild(config["server-id"])

    @property
    def db(self):
        return self.bot.get_cog("Database")

    @property
    def mail(self):
        return self.bot.get_cog("Mail")

    @property
    def __secret(self):
        if self.__secret_ is not None:
            return self.__secret_
        
        self.__secret_ = self.db.get_secret(SecretID.VERIFY)
        return self.__secret_

    @commands.group(name="verify")
    @botcore.perms.in_allowed_channel(error=True)
    @botcore.perms.is_unverified_user(error=True)
    async def cmd_verify(self, ctx):
        """Handle verify command.

        Begin verification process for member that invoked it, if they are not
        already verified.

        Args:
            ctx: Context object associated with command invocation.
        """
        if ctx.invoked_subcommand is None:
            await self.__proc_begin(ctx.author)

    @cmd_verify.command(name="approve")
    @botcore.perms.in_admin_channel(error=True)
    @botcore.perms.is_admin_user(error=True)
    async def cmd_verify_approve(self, ctx, member_id: int):
        """Handle execapprove command.

        Grant member verified rank, if they are currently awaiting exec
        approval.

        Args:
            ctx: Context object associated with command invocation.
            member_id: Discord ID of member to approve.
        """
        await self.__proc_exec_approve(self.guild.get_member(member_id))

    @cmd_verify.command(name="reject")
    @botcore.perms.in_admin_channel(error=True)
    @botcore.perms.is_admin_user(error=True)
    async def cmd_verify_reject(self, ctx, member_id: int, *, reason: str):
        """Handle execreject command.

        Reject member for verification and delete them from database, if they
        are currently awaiting exec approval.

        Args:
            ctx: Context object associated with command invocation.
            member_id: Discord ID of member to approve.
            reason: Rejection reason.
        """
        member = self.guild.get_member(member_id)
        reason = " ".join(reason)
        await self.__proc_exec_reject(member, reason)

    @commands.command(name="restart")
    @botcore.perms.in_dm_channel()
    @botcore.perms.is_guild_member(error=True)
    @botcore.perms.is_unverified_user()
    async def cmd_restart(self, ctx):
        """Handle restart command.

        Restart verification process for member that invoked it, if they are
        currently undergoing verification.

        Args:
            ctx: Context object associated with command invocation.
        """
        await self.__proc_restart(ctx.author)

    @commands.command(name="resend")
    @botcore.perms.in_dm_channel()
    @botcore.perms.is_guild_member(error=True)
    @botcore.perms.is_unverified_user()
    async def cmd_resend(self, ctx):
        """Handle resend command.

        Resend verification email to member that invoked it, if they were
        previously sent this email.

        Args:
            ctx: Context object associated with command invocation.
        """
        await self.__proc_resend_email(self.guild.get_member(ctx.author.id))

    @commands.Cog.listener()
    @botcore.perms.is_human()
    @botcore.perms.was_verified_user()
    async def on_member_join(self, member):
        """Handle member joining that was previously verified.

        Grant member verified rank.

        Args:
            member: Member object that joined the server.
        """
        await self.__proc_grant_rank(member)

    @commands.Cog.listener()
    @botcore.perms.in_dm_channel()
    @botcore.perms.is_human()
    @botcore.perms.is_not_command()
    @botcore.perms.is_guild_member()
    @botcore.perms.is_unverified_user()
    async def on_message(self, message):
        """Handle DM received by unverified member.

        If they are undergoing verification, process message in their FSM.

        Args:
            message: Message object received.
        """
        member = self.guild.get_member(message.author.id)
        if member.id in self.verifying:
            state = self.verifying[member.id][MemberKey.STATE]
            await self.__state_handler[state](member, message)

    def get_code(self, user):
        """Generate verification code for user.

        Args:
            user: User object to generate code for.

        Returns:
            Verification code as string of hex bytes.
        """
        msg = bytes(str(user.id), "utf8")
        return hmac.new(self.__secret, msg, "sha256").hexdigest()

    async def __proc_begin(self, member):
        """Begin verification process for member.

        Creates new entry in database.

        If member is already undergoing verification, send error message.

        Args:
            member: Member object to begin verifying.
        """
        if member.id in self.verifying:
            await member.send("You are already undergoing the verification "
                "process. To restart, type `!restart`.")
            return
        
        try:
            if self.db.get_member_data(member.id)[MemberKey.ID_VER]:
                await self.__proc_grant_rank(member)
                return
        except MemberNotFound:
            pass

        default_data = {
            MemberKey.STATE: None,
            MemberKey.NAME: None,
            MemberKey.ZID: None,
            MemberKey.EMAIL: None,
            MemberKey.EMAIL_VER: False,
            MemberKey.ID_VER: False
        }
        self.verifying[member.id] = default_data
        self.db.set_member_data(member.id, default_data)

        await self.__proc_request_name(member)

    async def __proc_restart(self, user):
        """Restart verification process for user.

        Args:
            user: User object to restart verification for.
        """
        if user.id not in self.verifying:
            await user.send("You are not currently being verified.")
            return

        del self.verifying[user.id]
        await self.__proc_begin(user)

    @_next_state(State.AWAIT_NAME)
    async def __proc_request_name(self, member):
        """DM name request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("What is your full name as it appears on your "
            "government-issued ID?\n"
            "You can restart this verification process at any time "
            "by typing `!restart`.")

    async def __state_await_name(self, member, message):
        """Handle message received from member while awaiting name.

        Proceed to request whether they are a UNSW student.

        Args:
            member: Member object that sent message.
            message: Message object received from member.
        """
        full_name = message.content
        self.db.update_member_data(member.id, {MemberKey.NAME: full_name})
        self.verifying[member.id][MemberKey.NAME] = full_name
        await self.__proc_request_unsw(member)

    @_next_state(State.AWAIT_UNSW)
    async def __proc_request_unsw(self, member):
        """DM is UNSW? request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("Are you a UNSW student? Please type `y` or `n`.")

    async def __state_await_unsw(self, member, message):
        """Handle message received from member while awaiting is UNSW?.

        If message is "y", proceed to request zID.
        If message is "n", proceed to request email address.
        If message is neither, send error message.

        Args:
            member: Member object that sent message.
            message: Message object received from member.
        """
        ans = message.content
        if ans == "y":
            await self.__proc_request_zid(member)
        elif ans == "n":
            await self.__proc_request_email(member)
        else:
            await member.send("Please type `y` or `n`.")

    @_next_state(State.AWAIT_ZID)
    async def __proc_request_zid(self, member):
        """DM zID request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("What is your 7 digit student number, "
            "not including the 'z' at the start?")
    
    async def __state_await_zid(self, member, message):
        """Handle message received from member while awaiting zID.

        If message is valid zID, proceed to email verification with their
        student email.

        Args:
            member: Member object that sent message.
            message: Message object received from member.
        """
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
            patch = {MemberKey.ZID: zid, MemberKey.EMAIL: email}
            self.db.update_member_data(member.id, patch)
            self.verifying[member.id].update(patch)

            await self.__proc_send_email(member)

    @_next_state(State.AWAIT_EMAIL)
    async def __proc_request_email(self, member):
        """DM email address request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("What is your email address?")

    async def __state_await_email(self, member, message):
        """Handle message received from member while awaiting email address.

        Assume message is email address and proceed to email verification.

        Args:
            member: Member object that sent message.
            message: Message object received from member.
        """
        email = message.content

        async with member.typing():
            patch = {MemberKey.EMAIL: email}
            self.db.update_member_data(member.id, patch)
            self.verifying[member.id].update(patch)

            await self.__proc_send_email(member)

    async def __proc_send_email(self, member):
        """Send verification code to member's email address.

        If email sends successfully, proceed to request code from member.

        Args:
            member: Member object to send email to.
        """
        email = self.verifying[member.id][MemberKey.EMAIL]
        code = self.get_code(member)

        try:
            self.mail.send_email(email, "Discord Verification", 
                f"Your code is {code}")
        except MailError:
            print(f"Failed to send email to {email}")
            await member.send("Oops! Something went wrong while attempting "
                "to send you an email. Please ensure that your details have "
                "been entered correctly.")
            return
        
        await self.__proc_request_code(member)

    @_next_state(State.AWAIT_CODE)
    async def __proc_request_code(self, member):
        """DM verification code request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("Please enter the code sent to your email "
            "(check your spam folder if you don't see it).\n"
            "You can request another email by typing `!resend`.")

    async def __state_await_code(self, member, message):
        """Handle message received from member while awaiting code.

        If message content is a code matching the code generated by us, proceed
        to grant verified rank to member if they are UNSW student, or request
        ID if they are non-UNSW.

        Args:
            member: Member object that sent message.
            message: Message object received from member.
        """
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
                await self.__proc_request_id(member)
            else:
                await self.__proc_grant_rank(member)

    async def __proc_resend_email(self, member):
        """Resend verification email to member's email address, if sent before.

        Args:
            member: Member object to resend email to.
        """
        if member.id in self.verifying \
            and self.verifying[member.id][MemberKey.STATE] \
            == self.State.AWAIT_CODE:
            await self.__proc_send_email(member)

    @_next_state(State.AWAIT_ID)
    async def __proc_request_id(self, member):
        """DM ID request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("Please send a message with a "
            "photo of your government-issued ID attached.")

    async def __state_await_id(self, member, message):
        """Handle message received from member while awaiting ID.
        
        If message has attachments, proceed to forward attachments to admins.

        Args:
            member: Member object that sent message.
            message: Message object received from member.
        """
        attachments = message.attachments
        if len(attachments) == 0:
            await member.send("No attachments received. Please try again.")
            return
        
        async with member.typing():
            await self.__proc_send_id_admins(member, attachments)

    @_next_state(State.AWAIT_APPROVAL)
    async def __proc_send_id_admins(self, member, attachments):
        """Forward member ID attachments to admin channel.

        Proceed to await exec approval or rejection of member.

        Args:
            member: Member object that sent attachments.
            attachments: List of Attachment objects received from member.
        """
        first_file = await attachments[0].to_file()
        admin_channel = self.guild.get_channel(config["admin-channel"])
        full_name = self.verifying[member.id][MemberKey.NAME]
        await admin_channel.send(f"Received attachment from {member.mention}. "
            f"Please verify that name on ID is `{full_name}`, "
            f"then type `!verify approve {member.id}` "
            f"or `!verify reject {member.id} \"reason\"`.", file=first_file)

        await member.send("Your attachment has been forwarded to the execs. "
            "Please wait.")

    async def __state_await_approval(self, member, message):
        """Handle message received from member while awaiting exec approval.

        Currently does nothing.

        Args:
            member: Member object that sent message.
            message: Message object received from member.
        """
        pass

    async def __proc_exec_approve(self, member):
        """Approve member awaiting exec approval.

        Will send error message if member not undergoing verification or not 
        awaiting exec approval.

        Proceed to grant member verified rank.

        Args:
            member: Member object to approve verification for.
        """
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

        await self.__proc_grant_rank(member)

    async def __proc_exec_reject(self, member, reason):
        """Reject member awaiting exec approval and send them reason.

        Deletes member from the database.

        Will send error message if member not undergoing verification or not 
        awaiting exec approval.

        Args:
            member: Member object to reject verification for.
            reason: String representing rejection reason.
        """
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

    async def __proc_grant_rank(self, member):
        """Grant verified rank to member and notify them and execs.

        Verified rank is defined in the cofig.

        Args:
            member: Member object to grant verified rank to.
        """
        self.db.update_member_data(member.id, {MemberKey.ID_VER: True})
        await member.add_roles(self.guild.get_role(config["verified-role"]))
        if member.id in self.verifying:
            del self.verifying[member.id]
        await member.send("You are now verified. Welcome to the server!")

        admin_channel = self.guild.get_channel(config["admin-channel"])
        await admin_channel.send(f"{member.mention} is now verified.")
