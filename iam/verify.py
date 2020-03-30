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
from time import time
import hmac
from discord.ext.commands import Cog, group, command
from discord import Member, NotFound
from logging import DEBUG, INFO

from iam.log import new_logger
from iam.db import MemberKey, SecretID, MemberNotFound
from iam.mail import MailError, is_valid_email
from iam.config import (
    PREFIX, SERVER_ID, VER_ROLE, ADMIN_CHANNEL, MAX_VER_EMAILS
)
from iam.hooks import (
    pre, post, check, log_attempt, log_invoke, log_success, is_verified_user,
    was_verified_user, is_unverified_user, never_verified_user, is_admin_user,
    is_guild_member, in_ver_channel, in_admin_channel, in_dm_channel, is_human,
    is_not_command
)

LOG = None
"""Logger for this module."""

COG_NAME = "Verify"
"""Name of this module's cog."""

def setup(bot):
    """Add Verify cog to bot.

    Args:
        bot: Bot object to add cog to.
    """
    global LOG
    LOG = new_logger(__name__)
    LOG.debug(f"Setting up {__name__} extension...")
    cog = Verify(bot, LOG)
    LOG.debug(f"Initialised {COG_NAME} cog")
    bot.add_cog(cog)
    LOG.debug(f"Added {COG_NAME} cog to bot")

def teardown(bot):
    """Remove Verify cog from this bot and remove logging.

    Args:
        bot: Bot object to remove cog from.
    """
    LOG.debug(f"Tearing down {__name__} extension")
    bot.remove_cog(COG_NAME)
    LOG.debug(f"Removed {COG_NAME} cog from bot")
    for handler in LOG.handlers:
        LOG.removeHandler(handler)

class State(IntEnum):
    """Enum representing all possible states in the Verify FSM."""
    AWAIT_NAME = 0
    AWAIT_UNSW = 1
    AWAIT_ZID = 2
    AWAIT_EMAIL = 3
    AWAIT_CODE = 4
    AWAIT_ID = 5
    AWAIT_APPROVAL = 6

def _next_state(state):
    """Decorate method to trigger state change on completion.

    Used with the Verify class to implement a finite state machine.

    Args:
        state: The state to transition to once function completes execution.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, member, *args):
            await func(self, member, *args)
            self.db.update_member_data(member.id, {MemberKey.VER_STATE: state})
        return wrapper
    return decorator

def _awaiting_approval(cog, ctx, member, *func_args, **func_kwargs):
    """Raises exception if member is not awaiting approval.
    
    Can only be used within the Verify cog.

    Args:
        func: Function invoked.
        cog: Verify cog.
        ctx: Context object associated with function invocation.
        member: Member to run check on.

    Raises:
        CheckFailed: If invoker does not have verified role.
    """
    try:
        member_data = cog.db.get_member_data(member.id)
    except MemberNotFound:
        return False, "That user is not currently being verified."
    if member_data[MemberKey.ID_VER]:
        return False, "That user is already verified."
    elif member_data[MemberKey.VER_STATE] != State.AWAIT_APPROVAL:
        return False, "That user is not awaiting approval."
    return True, None

class Verify(Cog, name=COG_NAME):
    """Handle automatic verification of server members.

    Verification process for each member implemented as a finite state machine.

    Attributes:
        State: Enum representing all possible states in the FSM.
        verifying: Dict of all members undergoing verification. Keys are member
                   Discord IDs and values are dicts containing state, name,
                   zID, email, email verified status and ID verified status.
                   Refer to iam.db.MemberKey.
        bot: Bot object that registered this cog.
        guild: Guild object associated with bot, defined in config.
        db: Database cog associated with bot.
        mail: Mail cog associated with bot.
    """

    def __init__(self, bot, logger):
        """Init cog with given bot.
        
        Args:
            bot: Bot object that registered this cog.
        """
        LOG.debug(f"Initialising {COG_NAME} cog...")
        self.bot = bot
        self.logger = logger
        self.__state_handler = [
            self.__state_await_name,
            self.__state_await_unsw,
            self.__state_await_zid,
            self.__state_await_email,
            self.__state_await_code,
            self.__state_await_id,
            self.__state_await_approval
        ]

    @property
    def guild(self):
        return self.bot.get_guild(SERVER_ID)

    @property
    def admin_channel(self):
        return self.guild.get_channel(ADMIN_CHANNEL)

    @property
    def db(self):
        return self.bot.get_cog("Database")

    @property
    def mail(self):
        return self.bot.get_cog("Mail")

    @group(
        name="verify",
        help="Begin verification process for user.",
        usage="",
        invoke_without_command=True,
        ignore_extra=False
    )
    async def grp_verify(self, ctx):
        """Register verify command group.
        
        Args:
            ctx: Context object associated with command invocation.
        """
        await self.cmd_verify(ctx)

    @pre(log_attempt())
    @pre(check(in_ver_channel, notify=True))
    @pre(check(is_unverified_user, notify=True))
    @pre(log_invoke())
    async def cmd_verify(self, ctx):
        """Handle verify command.

        Begin verification process for member that invoked it, if they are not
        already verified.

        Args:
            ctx: Context object associated with command invocation.
        """
        await self.__proc_begin(ctx.author)

    @grp_verify.command(
        name="approve",
        help="Verify a member awaiting exec approval.",
        usage="(Discord ID) __member__"
    )
    @pre(log_attempt())
    @pre(check(in_admin_channel, notify=True))
    @pre(check(is_admin_user, notify=True))
    @pre(log_invoke())
    @post(log_success())
    async def cmd_verify_approve(self, ctx, member: Member):
        """Handle verify approve command.

        Grant member verified rank, if they are currently awaiting exec
        approval.

        Args:
            ctx: Context object associated with command invocation.
            member_id: Discord ID of member to approve.
        """
        await self.__proc_exec_approve(ctx, member)

    @grp_verify.command(
        name="reject",
        help="Reject a member awaiting exec approval.",
        usage="(Discord ID) __member__ (multiple words) __reason__"
    )
    @pre(log_attempt())
    @pre(check(in_admin_channel, notify=True))
    @pre(check(is_admin_user, notify=True))
    @pre(log_invoke())
    @post(log_success())
    async def cmd_verify_reject(self, ctx, member: Member, 
        *, reason: str):
        """Handle verify reject command.

        Reject member for verification and delete them from database, if they
        are currently awaiting exec approval.

        Args:
            ctx: Context object associated with command invocation.
            member_id: Discord ID of member to approve.
            reason: Rejection reason.
        """
        await self.__proc_exec_reject(ctx, member, reason)

    @grp_verify.command(
        name="pending",
        help="Display list of members awaiting approval for verification.",
        usage=""
    )
    @pre(log_attempt())
    @pre(check(is_admin_user, notify=True))
    @pre(check(in_admin_channel, notify=True))
    @pre(log_invoke())
    @post(log_success())
    async def cmd_verify_pending(self, ctx):
        """Handle verify pending command.

        Display list of members currently awaiting exec approval.

        Message will be sent to admin channel defined in config.

        Args:
            ctx: Context object associated with command invocation.
        """
        await self.__proc_display_pending()

    @grp_verify.command(
        name="check",
        help="Retrieve stored photo of ID from member awaiting approval.",
        usage="(Discord ID) __member__"
    )
    @pre(log_attempt())
    @pre(check(in_admin_channel, notify=True))
    @pre(check(is_admin_user, notify=True))
    @pre(log_invoke())
    @post(log_success())
    async def cmd_verify_check(self, ctx, member: Member):
        """Handle verify check command.

        Resend ID attachments from member to admin channel defined in config.

        Args:
            ctx: Context object associated with command invocation.
        """
        try:
            member_data = self.db.get_member_data(member.id)
        except MemberNotFound:
            await member.send("You are not currently being verified.")
        await self.__proc_resend_id(ctx, member, member_data)

    @command(name="restart", hidden=True)
    @pre(log_attempt())
    @pre(check(in_dm_channel))
    @pre(check(is_guild_member, notify=True))
    @pre(check(is_unverified_user))
    @pre(log_invoke())
    @post(log_success())
    async def cmd_restart(self, ctx):
        """Handle restart command.

        Restart verification process for member that invoked it, if they are
        undergoing verification.

        Args:
            ctx: Context object associated with command invocation.
        """
        await self.__proc_restart(ctx.author)

    @command(name="resend", hidden=True)
    @pre(log_attempt())
    @pre(check(in_dm_channel))
    @pre(check(is_guild_member, notify=True))
    @pre(check(is_unverified_user))
    @pre(log_invoke())
    @post(log_success())
    async def cmd_resend(self, ctx):
        """Handle resend command.

        Resend verification email to member that invoked it, if they were
        previously sent this email.

        Args:
            ctx: Context object associated with command invocation.
        """
        member = self.guild.get_member(ctx.author.id)
        try:
            member_data = self.db.get_member_data(member.id)
        except MemberNotFound:
            await member.send("You are not currently being verified.")
        await self.__proc_resend_email(member, member_data)

    @Cog.listener()
    @pre(check(is_human, level=None))
    @pre(check(was_verified_user, level=None))
    @pre(log_invoke("was verified"))
    @post(log_success("was verified"))
    async def on_member_join(self, member):
        """Handle member joining that was previously verified.

        Grant member verified rank.

        Args:
            member: Member object that joined the server.
        """
        await self.__proc_grant_rank(member)
        await self.admin_channel.send(f"{member.mention} was previously "
            "verified, and has automatically been granted the verified rank "
            "upon (re)joining the server.")

    @Cog.listener()
    @pre(check(is_human, level=None))
    @pre(check(in_dm_channel, level=None))
    @pre(check(is_guild_member, level=None))
    @pre(check(is_unverified_user, level=None))
    @pre(log_invoke(meta="verifying"))
    @post(log_success(meta="verifying"))
    async def on_message(self, message):
        """Handle DM received by unverified member.

        If they are undergoing verification, process message in their FSM.

        Args:
            message: Message object received.
        """
        if message.content == "?restart" or message.content == "?resend":
            return
        member = self.guild.get_member(message.author.id)
        try:
            member_data = self.db.get_member_data(member.id)
        except MemberNotFound:
            return
        if not member_data[MemberKey.ID_VER]:
            state = member_data[MemberKey.VER_STATE]
            await self.__state_handler[state](member, member_data, message)

    @pre(log_invoke(level=DEBUG))
    @post(log_success())
    def get_code(self, user, noise):
        """Generate verification code for user.

        Args:
            user: User object to generate code for.
            noise: Number to add to user ID when hashing.

        Returns:
            Verification code as string of hex bytes.
        """
        secret = self.db.get_secret(SecretID.VERIFY)
        user_bytes = bytes(str(user.id + noise), "utf8")
        return hmac.new(secret, user_bytes, "sha256").hexdigest()

    @pre(log_invoke())
    @post(log_success())
    async def __proc_begin(self, member):
        """Begin verification process for member.

        Creates new entry in database.

        If member is already undergoing verification, send error message.

        If member was previously verified, immediately proceed to grant them
        the verified rank.

        Args:
            member: Member object to begin verifying.
        """
        try:
            member_data = self.db.get_member_data(member.id)
        except MemberNotFound:
            self.db.set_member_data(member.id, {
                MemberKey.NAME: None,
                MemberKey.ZID: None,
                MemberKey.EMAIL: None,
                MemberKey.EMAIL_ATTEMPTS: 0,
                MemberKey.EMAIL_VER: False,
                MemberKey.ID_MESSAGE: None,
                MemberKey.ID_VER: False,
                MemberKey.VER_EXEC: None,
                MemberKey.VER_STATE: None,
                MemberKey.VER_TIME: time(),
                MemberKey.MAX_EMAIL_ATTEMPTS: MAX_VER_EMAILS
            })
        else:
            if member_data[MemberKey.ID_VER]:
                LOG.info(f"Member {member} was already verified. "
                    "Granting rank...")
                await self.__proc_grant_rank(member)
                await member.send("Our records show you were verified in the "
                    "past. You have been granted the rank once again. Welcome "
                    "back to the server!")
                await self.admin_channel.send(f"{member.mention} was "
                    "previously verified, and has been given the verified "
                    "rank again through request.")
                return
            elif member_data[MemberKey.VER_STATE] is not None:
                LOG.debug(f"Member {member} already undergoing verification. "
                    "Notifying them to use the restart command...")     
                await member.send("You are already undergoing the "
                    "verification process. To restart, type "
                    f"`{PREFIX}restart`.")
                return
            else:
                email_attempts = member_data[MemberKey.EMAIL_ATTEMPTS]
                max_email_attempts = member_data[MemberKey.MAX_EMAIL_ATTEMPTS]
                if email_attempts >= max_email_attempts:
                    # Member was previously rejected but ran out of email
                    # verification attempts. Grant them 2 more.
                    self.db.update_member_data(member.id, {
                        MemberKey.MAX_EMAIL_ATTEMPTS: max_email_attempts + 2
                    })

        await self.__proc_request_name(member)

    @pre(log_invoke())
    @post(log_success())
    async def __proc_restart(self, user):
        """Restart verification process for user.

        If user already verified or not undergoing verification, send error
        message to user.

        Args:
            user: User object to restart verification for.
        """
        try:
            member_data = self.db.get_member_data(user.id)
        except MemberNotFound:
            await user.send("You are not currently being verified.")
            return
        if member_data[MemberKey.ID_VER]:
            await user.send("You are already verified.")
            return
        elif member_data[MemberKey.VER_STATE] is None:
            await user.send("You are not currently being verified.")
            return

        async with user.typing():
            self.db.update_member_data(user.id, {
                MemberKey.VER_STATE: None,
                MemberKey.VER_TIME: time()
            })

        await self.__proc_request_name(user)

    @_next_state(State.AWAIT_NAME)
    @pre(log_invoke())
    @post(log_success())
    async def __proc_request_name(self, member):
        """DM name request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("What is your full name as it appears on your "
            "government-issued ID?\nYou can restart this verification process "
            f"at any time by typing `{PREFIX}restart`.")

    @pre(log_invoke())
    @post(log_success())
    async def __state_await_name(self, member, member_data, message):
        """Handle message received from member while awaiting name.

        Proceed to request whether they are a UNSW student.

        Args:
            member: Member object that sent message.
            member_data: Dict containing data from member entry in database.
            message: Message object received from member.
        """
        full_name = message.content
        MAX_NAME_LEN = 500
        if len(full_name) > MAX_NAME_LEN:
            await member.send(f"Name must be {MAX_NAME_LEN} characters "
                "or fewer. Please try again.")
            return

        self.db.update_member_data(member.id, {MemberKey.NAME: full_name})
        await self.__proc_request_unsw(member)

    @_next_state(State.AWAIT_UNSW)
    @pre(log_invoke())
    @post(log_success())
    async def __proc_request_unsw(self, member):
        """DM is UNSW? request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("Are you a UNSW student? Please type `y` or `n`.")

    @pre(log_invoke())
    @post(log_success())
    async def __state_await_unsw(self, member, member_data, message):
        """Handle message received from member while awaiting is UNSW?.

        If message is "y", proceed to request zID.
        If message is "n", proceed to request email address.
        If message is neither, send error message.

        Args:
            member: Member object that sent message.
            member_data: Dict containing data from member entry in database.
            message: Message object received from member.
        """
        ans = message.content.lower()
        if ans == "y" or ans == "yes":
            await self.__proc_request_zid(member)
        elif ans == "n" or ans == "no":
            await self.__proc_request_email(member)
        else:
            await member.send("Please type `y` or `n`.")

    @_next_state(State.AWAIT_ZID)
    @pre(log_invoke())
    @post(log_success())
    async def __proc_request_zid(self, member):
        """DM zID request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("What is your 7 digit student number, "
            "not including the 'z' at the start?")
    
    @pre(log_invoke())
    @post(log_success())
    async def __state_await_zid(self, member, member_data, message):
        """Handle message received from member while awaiting zID.

        If message is valid zID, proceed to email verification with their
        student email.

        Args:
            member: Member object that sent message.
            member_data: Dict containing data from member entry in database.
            message: Message object received from member.
        """
        zid = message.content
        ZID_LEN = 7
        if len(zid) != ZID_LEN:
            await member.send(f"Your response must be {ZID_LEN} "
                "characters long. Please try again.")
            return
        try:
            zid = int(zid)
        except ValueError:
            await member.send("Your response must be an integer. "
                "Please try again.")
            return
        email = f"z{zid}@student.unsw.edu.au"

        self.db.update_member_data(member.id, {
            MemberKey.ZID: zid,
            MemberKey.EMAIL: email
        })

        await self.__proc_send_email(member, member_data, email)

    @_next_state(State.AWAIT_EMAIL)
    @pre(log_invoke())
    @post(log_success())
    async def __proc_request_email(self, member):
        """DM email address request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("What is your email address?")

    @pre(log_invoke())
    @post(log_success())
    async def __state_await_email(self, member, member_data, message):
        """Handle message received from member while awaiting email address.

        Assume message is email address and proceed to email verification.

        Args:
            member: Member object that sent message.
            member_data: Dict containing data from member entry in database.
            message: Message object received from member.
        """
        email = message.content
        if not is_valid_email(email):
            await member.send("That is not a valid email address. "
                "Please try again.")
            return

        await self.__proc_send_email(member, member_data, email)

    @pre(log_invoke())
    @post(log_success())
    async def __proc_send_email(self, member, member_data, email):
        """Send verification code to member's email address.

        If email sends successfully, proceed to request code from member.

        Args:
            member: Member object to send email to.
            member_data: Dict containing data from member entry in database.
            email: Member's email address.
        """
        email_attempts = member_data[MemberKey.EMAIL_ATTEMPTS]
        max_email_attempts = member_data[MemberKey.MAX_EMAIL_ATTEMPTS]
        if email_attempts >= max_email_attempts:
            await member.send("You have requested too many emails. "
                "Please DM an exec to continue verification.")
            return

        code = self.get_code(member, member_data[MemberKey.VER_TIME])

        try:
            async with member.typing():
                self.mail.send_email(email, "PCSoc Discord Verification", 
                    f"Your code is {code}")
        except MailError as err:
            err.notify()
            await member.send("Oops! Something went wrong while attempting "
                "to send you an email. Please ensure that your details have "
                "been entered correctly.")
            return

        self.db.update_member_data(member.id, {
            MemberKey.EMAIL: email,
            MemberKey.EMAIL_ATTEMPTS: email_attempts + 1
        })
        
        await self.__proc_request_code(member)

    @_next_state(State.AWAIT_CODE)
    @pre(log_invoke())
    @post(log_success())
    async def __proc_request_code(self, member):
        """DM verification code request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("Please enter the code sent to your email "
            "(check your spam folder if you don't see it).\n"
            f"You can request another email by typing `{PREFIX}resend`.")

    @pre(log_invoke())
    @post(log_success())
    async def __state_await_code(self, member, member_data, message):
        """Handle message received from member while awaiting code.

        If message content is a code matching the code generated by us, proceed
        to grant verified rank to member if they are UNSW student, or request
        ID if they are non-UNSW.

        Args:
            member: Member object that sent message.
            member_data: Dict containing data from member entry in database.
            message: Message object received from member.
        """
        received_code = message.content
        expected_code = self.get_code(member, member_data[MemberKey.VER_TIME])
        if not hmac.compare_digest(received_code, expected_code):
            await member.send("That was not the correct code. Please try "
                "again.\nYou can request another email by typing "
                f"`{PREFIX}resend`.")
            return

        self.db.update_member_data(member.id, {
            MemberKey.EMAIL_VER: True,
            MemberKey.VER_TIME: time()
        })
        
        if member_data[MemberKey.ZID] is None:
            await self.__proc_request_id(member)
        else:
            await self.__proc_grant_rank(member)

    @pre(log_invoke())
    @post(log_success())
    async def __proc_resend_email(self, member, member_data):
        """Resend verification email to member's email address, if sent before.

        Args:
            member: Member object to resend email to.
            member_data: Dict containing data from member entry in database.
        """
        if not member_data[MemberKey.ID_VER] \
            and member_data[MemberKey.VER_STATE] == State.AWAIT_CODE:
            email = member_data[MemberKey.EMAIL]
            await self.__proc_send_email(member, member_data, email)

    @_next_state(State.AWAIT_ID)
    @pre(log_invoke())
    @post(log_success())
    async def __proc_request_id(self, member):
        """DM ID request to member and await response.

        Args:
            member: Member object to make request to.
        """
        await member.send("Please send a message with a "
            "photo of your government-issued ID attached.")

    @pre(log_invoke())
    @post(log_success())
    async def __state_await_id(self, member, member_data, message):
        """Handle message received from member while awaiting ID.
        
        If message has attachments, proceed to forward attachments to admins.

        Args:
            member: Member object that sent message.
            member_data: Dict containing data from member entry in database.
            message: Message object received from member.
        """
        attachments = message.attachments
        if len(attachments) == 0:
            await member.send("No attachments received. Please try again.")
            return
        
        await self.__proc_forward_id_admins(member, member_data, attachments)

    @_next_state(State.AWAIT_APPROVAL)
    @pre(log_invoke())
    @post(log_success())
    async def __proc_forward_id_admins(self, member, member_data, attachments):
        """Forward member ID attachments to admin channel.

        Proceed to await exec approval or rejection of member.

        Args:
            member: Member object that sent attachments.
            attachments: List of Attachment objects received from member.
        """
        full_name = member_data[MemberKey.NAME]
        async with member.typing():
            files = [await a.to_file() for a in attachments]
            message = await self.admin_channel.send("Received attachment(s) "
                f"from {member.mention}. Please verify that name on ID is "
                f"`{full_name}`, then type `{PREFIX}verify approve "
                f"{member.id}` or `{PREFIX}verify reject {member.id} "
                "\"reason\"`.", files=files)

        self.db.update_member_data(member.id, {
            MemberKey.ID_MESSAGE: message.id
        })

        await member.send("Your attachment(s) have been forwarded to the "
            "execs. Please wait.")

    @pre(log_invoke())
    @post(log_success())
    async def __state_await_approval(self, member, member_data, message):
        """Handle message received from member while awaiting exec approval.

        Currently does nothing.

        Args:
            member: Member object that sent message.
            message: Message object received from member.
        """
        pass

    @pre(check(_awaiting_approval, notify=True))
    @pre(log_invoke())
    @post(log_success())
    async def __proc_exec_approve(self, ctx, member):
        """Approve member awaiting exec approval.

        Proceed to grant member verified rank.

        Args:
            ctx: Context object associated with command invocation.
            member: Member object to approve verification for.
        """
        self.db.update_member_data(member.id, {
            MemberKey.VER_EXEC: ctx.author.id
        })
        await self.__proc_grant_rank(member)

    @pre(check(_awaiting_approval, notify=True))
    @pre(log_invoke())
    @post(log_success())
    async def __proc_exec_reject(self, ctx, member, reason):
        """Reject member awaiting exec approval and send them reason.

        Deletes member from the database.

        Args:
            ctx: Context object associated with command invocation.
            member: Member object to reject verification for.
            reason: String representing rejection reason.
        """
        self.db.update_member_data(member.id, {
            MemberKey.VER_STATE: None
        })

        await member.send("Your verification request has been denied "
            f"for the following reason(s): `{reason}`.\n"
            f"You can start a new request by typing `{PREFIX}verify` in the "
            "verification channel.")

        await self.admin_channel.send("Rejected verification request from "
            f"{member.mention}.")

    @pre(log_invoke())
    @post(log_success())
    async def __proc_display_pending(self):
        """Display list of members currently awaiting exec approval.

        Message will be sent to admin channel defined in config.
        """
        mentions = []
        verifying = self.db.get_unverified_members_data()
        for member_id in verifying:
            if verifying[member_id][MemberKey.VER_STATE] \
                == State.AWAIT_APPROVAL:
                member = self.guild.get_member(member_id)
                mentions.append(f"{member.mention}: {member_id}")
        
        if len(mentions) == 0:
            await self.admin_channel.send("No members currently awaiting "
            "approval.")
            return

        mentions_formatted = "\n".join(mentions)
        await self.admin_channel.send("__Members awaiting approval:__\n"
            f"{mentions_formatted}")

    @pre(check(_awaiting_approval, notify=True))
    @pre(log_invoke())
    @post(log_success())
    async def __proc_resend_id(self, ctx, member, member_data):
        """Resend ID attachments from member to admin channel.

        Admin channel defined in config.

        Retrieves attachments from previous message in admin channel.

        Send error message if previous message was deleted.

        Args:
            ctx: Context object associated with command invocation.
            member: Member object to retrieve ID attachments from.
            member_data: Dict containing data from member entry in database.
        """
        message_id = member_data[MemberKey.ID_MESSAGE]
        try:
            message = await self.admin_channel.fetch_message(message_id)
        except NotFound:
            await self.admin_channel.send("Could not find previous message in "
            "this channel containing attachments! Perhaps it was deleted?")
            return
        attachments = message.attachments

        async with self.admin_channel.typing():
            files = [await a.to_file() for a in attachments]
            full_name = member_data[MemberKey.NAME]
            await self.admin_channel.send("Previously received attachment(s) "
                f"from {member.mention}. Please verify that name on ID is "
                f"`{full_name}`, then type `{PREFIX}verify approve "
                f"{member.id}` or `{PREFIX}verify reject {member.id} "
                "\"reason\"`.", files=files)

    @pre(log_invoke())
    @post(log_success())
    async def __proc_grant_rank(self, member):
        """Grant verified rank to member and notify them and execs.

        Verified rank is defined in the cofig.

        Args:
            member: Member object to grant verified rank to.
        """
        self.db.update_member_data(member.id, {MemberKey.ID_VER: True})
        await member.add_roles(self.guild.get_role(VER_ROLE))
        LOG.info(f"Granted verified rank to member '{member.id}'")
        await member.send("You are now verified. Welcome to the server!")
        await self.admin_channel.send(f"{member.mention} is now verified.")
