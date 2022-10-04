"""Handle automatic verification of server members."""

from enum import IntEnum
from functools import wraps
from time import time
from re import search
import hmac
# from discord.ext.commands import Cog, group, command
# from discord import Member, NotFound
from nextcord.ext.commands import Cog, group, command
from nextcord import  Member, NotFound
from logging import DEBUG

from iam.log import new_logger
from iam.db import MemberKey, make_def_member_data, SecretID, MemberNotFound
from iam.mail import MailError, is_valid_email
from iam.config import (
    PREFIX,
    SERVER_ID,
    VERIF_ROLE,
    ADMIN_CHANNEL,
    JOIN_ANNOUNCE_CHANNEL,
    MAX_VER_EMAILS,
)
from iam.hooks import (
    pre,
    post,
    check,
    CheckResult,
    log_attempt,
    log_invoke,
    log_success,
    has_verified_role,
    was_verified_user,
    is_unverified_user,
    never_verified_user,
    is_admin_user,
    is_guild_member,
    in_ver_channel,
    in_admin_channel,
    in_dm_channel,
    is_human,
    is_not_command,
)

LOG = new_logger(__name__)
"""Logger for this module."""

COG_NAME = "Verify"
"""Name of this module's cog."""

ZID_REGEX = r"^[zZ][0-9]{7}$"
"""Any string that matches this regex is a valid zID."""


def setup(bot):
    """Add Verify cog to bot.

    Args:
        bot: Bot object to add cog to.
    """
    LOG.debug(f"Setting up {__name__} extension...")
    cog = Verify(bot, LOG)
    LOG.debug(f"Initialised {COG_NAME} cog")
    bot.add_cog(cog)
    LOG.debug(f"Added {COG_NAME} cog to bot")


def teardown(bot):
    """Remove Verify cog from this bot.

    Args:
        bot: Bot object to remove cog from.
    """
    LOG.debug(f"Tearing down {__name__} extension")
    bot.remove_cog(COG_NAME)
    LOG.debug(f"Removed {COG_NAME} cog from bot")


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
        async def wrapper(db, member, *args):
            await func(db, member, *args)
            db.update_member_data(member.id, {MemberKey.VER_STATE: state})

        return wrapper

    return decorator


def _awaiting_approval(db, ctx, member, *args, **kwargs):
    """Raises exception if member is not awaiting approval.
    
    Can only be used within the Verify cog.

    Args:
        db: Database object.
        ctx: Context object associated with function invocation.
        member: Member to run check on.

    Raises:
        CheckFailed: If invoker does not have verified role.
    """
    try:
        member_data = db.get_member_data(member.id)
    except MemberNotFound:
        return CheckResult(False, "That user is not currently being verified.")
    if member_data[MemberKey.ID_VER]:
        return CheckResult(False, "That user is already verified.")
    elif member_data[MemberKey.VER_STATE] != State.AWAIT_APPROVAL:
        return CheckResult(False, "That user is not awaiting approval.")
    return CheckResult(True, None)


def is_valid_zid(zid):
    """Returns whether given string is a valid zID.

    Args:
        zid: String to validate.

    Returns:
        Boolean value representing whether string is a valid zID.
    """
    return search(ZID_REGEX, zid) is not None


def is_verifying_user(cog, ctx, *args, **kwargs):
    """Checks that user that invoked function is undergoing verification.

    Associated cog must have db as an instance variable.

    Args:
        func: Function invoked.
        cog: Cog associated with function invocation.
        ctx: Context object associated with function invocation.

    Raises:
        CheckFailed: If invoker does not have verified role.
    """
    try:
        member_data = cog.db.get_member_data(ctx.author.id)
    except MemberNotFound:
        return False, "You are not currently being verified."
    if member_data[MemberKey.VER_STATE] is None:
        return False, "You are not currently being verified."
    elif member_data[MemberKey.ID_VER]:
        return False, "You are already verified."
    return True, None


@pre(log_invoke(LOG, level=DEBUG))
@post(log_success(LOG))
def get_code(db, user, noise):
    """Generate verification code for user.

    Args:
        db: Database object.
        user: User object to generate code for.
        noise: Number to add to user ID when hashing.

    Returns:
        Verification code as string of hex bytes.
    """
    secret = db.get_secret(SecretID.VERIFY)
    user_bytes = bytes(str(user.id + noise), "utf8")
    return hmac.new(secret, user_bytes, "sha256").hexdigest()


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_begin(invoke_message, db, ver_role, admin_channel, member):
    """Begin verification process for member.

    Creates new entry in database.

    If member is already undergoing verification, send error message.

    If member was previously verified, immediately proceed to grant them
    the verified rank.

    Args:
        invoke_message: Message associated with process invocation.
        db: Database object.
        ver_role: Verified role object to grant to members.
        ver_channel: Channel object to send check DMs instruction to.
        admin_channel: Channel object to send exec notifications to.
        member: Member object to begin verifying.
    """
    try:
        member_data = db.get_member_data(member.id)
    except MemberNotFound:
        db.set_member_data(member.id, make_def_member_data())
    else:
        if member_data[MemberKey.ID_VER]:
            LOG.info(f"Member {member} was already verified. " "Granting rank...")
            await proc_grant_rank(ver_role, admin_channel, member, silent=True)
            await member.send(
                "Our records show you were verified in the "
                "past. You have been granted the rank once again. Welcome "
                "back to the server!"
            )
            await admin_channel.send(
                f"{member.mention} was "
                "previously verified, and has been given the verified "
                "rank again through request."
            )
            return
        elif member_data[MemberKey.VER_STATE] is not None:
            LOG.debug(
                f"Member {member} already undergoing verification. "
                "Notifying them to use the restart command..."
            )
            await member.send(
                "You are already undergoing the "
                "verification process. To restart, type "
                f"`{PREFIX}restart`."
            )
            return
        else:
            email_attempts = member_data[MemberKey.EMAIL_ATTEMPTS]
            max_email_attempts = member_data[MemberKey.MAX_EMAIL_ATTEMPTS]
            if email_attempts >= max_email_attempts:
                # Member was previously rejected but ran out of email
                # verification attempts. Grant them 2 more.
                db.update_member_data(
                    member.id, {MemberKey.MAX_EMAIL_ATTEMPTS: max_email_attempts + 2}
                )

    await invoke_message.reply("Please check your DMs for a message from me.")
    await proc_request_name(db, member)


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_restart(db, user):
    """Restart verification process for user.

    If user already verified or not undergoing verification, send error
    message to user.

    Args:
        db: Database object.
        user: User object to restart verification for.
    """
    try:
        member_data = db.get_member_data(user.id)
    except MemberNotFound:
        await user.send("You are not currently being verified.")
        return
    if member_data[MemberKey.ID_VER]:
        await user.send("You are already verified.")
        return
    elif member_data[MemberKey.VER_STATE] is None:
        await user.send("You are not currently being verified.")
        return
    elif member_data[MemberKey.VER_STATE] in [State.AWAIT_ID, State.AWAIT_APPROVAL]:
        await user.send("You cannot restart after verifying your email!")
        return

    async with user.typing():
        db.update_member_data(
            user.id, {MemberKey.VER_STATE: None, MemberKey.VER_TIME: time()}
        )

    await proc_request_name(db, user)


@_next_state(State.AWAIT_NAME)
@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_request_name(db, member):
    """DM name request to member and await response.

    Args:
        member: Member object to make request to.
    """
    await member.send(
        "Arc - UNSW Student Life strongly recommends all student societies verify their members' identities before allowing them to interact with their online communities (Arc Clubs Handbook section 22.2)\n"
        "\n"
        "To send messages in our PCSoc Discord server, we require the following:\n"
        "(1) Your full name\n"
        "(2) Whether or not you're a student at UNSW\n"
        "  (2a) If yes, your UNSW-issued zID\n"
        "\n"
        "  (2b) If not, your email address\n"
        "  (3b) Your government-issued photo ID (e.g. driver's license or photo card).\n"
        "\n"
        "The information you share with us is only accessible by our current executive team - we do not share this with any other parties. You may request to have your record deleted if you are no longer a member of PCSoc.\n"
        "If you have questions or you're stuck, feel free to message any of our executives :)\n"
        "-----\n"
        "(1) What is your full name as it appears on your government-issued ID?\n"
        "You can restart this verification process "
        f"at any time by typing `{PREFIX}restart`."
    )


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def state_await_name(db, member, full_name):
    """Handle full name received from member while awaiting name.

    Proceed to request whether they are a UNSW student.

    Args:
        db: Database object.
        member: Member object that sent message.
        member_data: Dict containing data from member entry in database.
        full_name: Message string received from member.
    """
    MAX_NAME_LEN = 500
    if len(full_name) > MAX_NAME_LEN:
        await member.send(
            f"Name must be {MAX_NAME_LEN} characters " "or fewer. Please try again."
        )
        return

    db.update_member_data(member.id, {MemberKey.NAME: full_name})
    await proc_request_unsw(db, member)


@_next_state(State.AWAIT_UNSW)
@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_request_unsw(db, member):
    """DM is UNSW? request to member and await response.

    Args:
        member: Member object to make request to.
    """
    await member.send("(2) Are you a UNSW student? Please type `y` or `n`.")


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def state_await_unsw(db, member, ans):
    """Handle answer received from member while awaiting is UNSW?.

    If ans is "y", proceed to request zID.
    If ans is "n", proceed to request email address.
    If ans is neither, send error message.
    ans is case insensitive.

    Args:
        db: Database object.
        member: Member object that sent message.
        member_data: Dict containing data from member entry in database.
        ans: Message string received from member.
    """
    ans = ans.lower()
    if ans == "y" or ans == "yes":
        await proc_request_zid(db, member)
    elif ans == "n" or ans == "no":
        await proc_request_email(db, member)
    else:
        await member.send("Please type `y` or `n`.")


@_next_state(State.AWAIT_ZID)
@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_request_zid(db, member):
    """DM zID request to member and await response.

    Args:
        member: Member object to make request to.
    """
    await member.send("(2a) What is your zID?")


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def state_await_zid(db, mail, member, member_data, zid):
    """Handle zID received from member while awaiting zID.

    If zid is valid zID, proceed to email verification with their student
    email.

    Args:
        db: Database object.
        mail: Mail object.
        member: Member object that sent message.
        member_data: Dict containing data from member entry in database.
        zid: Message string received from member.
    """
    zid = zid.lower()
    if not is_valid_zid(zid):
        await member.send(
            "Your zID must match the following format: " "`zXXXXXXX`. Please try again"
        )
        return
    email = f"{zid}@student.unsw.edu.au"

    db.update_member_data(member.id, {MemberKey.ZID: zid, MemberKey.EMAIL: email})

    await proc_send_email(db, mail, member, member_data, email)


@_next_state(State.AWAIT_EMAIL)
@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_request_email(db, member):
    """DM email address request to member and await response.

    Args:
        member: Member object to make request to.
    """
    await member.send("(2b) What is your email address?")


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def state_await_email(db, mail, member, member_data, email):
    """Handle email address received from member while awaiting email address.

    Assume email represents an email address and proceed to email verification.

    Args:
        db: Database object.
        mail: Mail object.
        member: Member object that sent message.
        member_data: Dict containing data from member entry in database.
        email: Message string received from member.
    """
    if not is_valid_email(email):
        await member.send("That is not a valid email address. " "Please try again.")
        return

    db.update_member_data(member.id, {MemberKey.EMAIL: email})

    await proc_send_email(db, mail, member, member_data, email)


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_send_email(db, mail, member, member_data, email):
    """Send verification code to member's email address.

    If email sends successfully, proceed to request code from member.

    Args:
        db: Database object.
        mail: Mail object.
        member: Member object to send email to.
        member_data: Dict containing data from member entry in database.
        email: Member's email address.
    """
    email_attempts = member_data[MemberKey.EMAIL_ATTEMPTS]
    max_email_attempts = member_data[MemberKey.MAX_EMAIL_ATTEMPTS]
    if email_attempts >= max_email_attempts:
        await member.send(
            "You have requested too many emails. "
            "Please DM an exec to continue verification."
        )
        return

    code = get_code(db, member, member_data[MemberKey.VER_TIME])

    try:
        async with member.typing():
            mail.send_email(email, "PCSoc Discord Verification", f"Your code is {code}")
    except MailError as err:
        err.notify()
        await member.send(
            "Oops! Something went wrong while attempting "
            "to send you an email. Please ensure that your details have "
            "been entered correctly."
        )
        return

    db.update_member_data(member.id, {MemberKey.EMAIL_ATTEMPTS: email_attempts + 1})

    await proc_request_code(db, member)


@_next_state(State.AWAIT_CODE)
@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_request_code(db, member):
    """DM verification code request to member and await response.

    Args:
        member: Member object to make request to.
    """
    await member.send(
        "Please enter the code sent to your email. If you are a "
        "UNSW student, this is your zID@student.unsw.edu.au email. Please "
        "check your spam folder if you don't see it.\n"
        f"You can request another email by typing `{PREFIX}resend`."
    )


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def state_await_code(
    db,
    ver_role,
    admin_channel,
    join_announce_channel,
    member,
    member_data,
    received_code,
):
    """Handle code received from member while awaiting code.

    If received_code matches the code generated by us, proceed to grant 
    verified rank to member if they are UNSW student, or request ID if they
    are non-UNSW.

    Args:
        db: Database object.
        ver_role: Verified role to grant to member.
        admin_channel: Channel object to send exec notification to.
        join_announce_channel: Channel object to send join announcements to.
        member: Member object that sent message.
        member_data: Dict containing data from member entry in database.
        received_code: Message string received from member.
    """
    expected_code = get_code(db, member, member_data[MemberKey.VER_TIME])
    if not hmac.compare_digest(received_code, expected_code):
        await member.send(
            "That was not the correct code. Please try "
            "again.\nYou can request another email by typing "
            f"`{PREFIX}resend`."
        )
        return

    db.update_member_data(
        member.id, {MemberKey.EMAIL_VER: True, MemberKey.VER_TIME: time()}
    )

    if member_data[MemberKey.ZID] is None:
        await proc_request_id(db, member)
    else:
        db.update_member_data(member.id, {MemberKey.ID_VER: True})
        await proc_grant_rank(ver_role, admin_channel, join_announce_channel, member)


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_resend_email(db, mail, member, member_data):
    """Resend verification email to user's email address, if sent before.

    Args:
        db: Database object.
        mail: Mail object.
        member: User object to resend email to.
        member_data: Dict containing data from member entry in database.
    """
    if (
        not member_data[MemberKey.ID_VER]
        and member_data[MemberKey.VER_STATE] == State.AWAIT_CODE
    ):
        email = member_data[MemberKey.EMAIL]
        await proc_send_email(db, mail, member, member_data, email)


@_next_state(State.AWAIT_ID)
@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_request_id(db, member):
    """DM ID request to member and await response.

    Args:
        member: Member object to make request to.
    """
    await member.send(
        "(3b) Please send a message with a "
        "photo of your government-issued ID attached."
    )


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def state_await_id(db, admin_channel, member, member_data, attachments):
    """Handle message received from member while awaiting ID.
    
    If message has attachments, proceed to forward attachments to admins.

    Args:
        db: Database object.
        admin_channel: Channel object to forward attachments to.
        member: Member object that sent message.
        member_data: Dict containing data from member entry in database.
        attachments: List of Attachment object received from member.
    """
    if len(attachments) == 0:
        await member.send("No attachments received. Please try again.")
        return

    await proc_forward_id_admins(db, member, admin_channel, member_data, attachments)


@_next_state(State.AWAIT_APPROVAL)
@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_forward_id_admins(db, member, admin_channel, member_data, attachments):
    """Forward member ID attachments to admin channel.

    Proceed to await exec approval or rejection of member.

    Args:
        db: Database object.
        member: Member object that sent attachments.
        admin_channel: Channel object to forward attachments to.
        member_data: Dict containing data from member entry in database.
        attachments: List of Attachment objects received from member.
    """
    full_name = member_data[MemberKey.NAME]
    async with member.typing():
        files = [await a.to_file() for a in attachments]
        message = await admin_channel.send(
            "Received attachment(s) "
            f"from {member.mention}. Please verify that name on ID is "
            f"`{full_name}`, then type `{PREFIX}verify approve "
            f"{member.id}` or `{PREFIX}verify reject {member.id} "
            '"reason"`.',
            files=files,
        )

    db.update_member_data(member.id, {MemberKey.ID_MESSAGE: message.id})

    await member.send(
        "Your attachment(s) have been forwarded to the " "execs. Please wait."
    )


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def state_await_approval():
    """Handle message received from member while awaiting exec approval.

    Currently does nothing.

    Args:
        member: Member object that sent message.
        message: Message object received from member.
    """
    pass


@pre(check(_awaiting_approval, notify=True))
@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_exec_approve(db, channel, member, join_announce_channel, exec, ver_role):
    """Approve member awaiting exec approval.

    Proceed to grant member verified rank.

    Args:
        db: Database object.
        channel: Channel object associated with command invocation.
        member: Member object to approve verification for.
        join_announce_channel: Channel object to send join announcements to.
        exec: Member object representing approving exec.
        ver_role: Verified role to grant to member.
    """
    db.update_member_data(
        member.id, {MemberKey.ID_VER: True, MemberKey.VER_EXEC: exec.id}
    )
    await proc_grant_rank(ver_role, channel, join_announce_channel, member)


@pre(check(_awaiting_approval, notify=True))
@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_exec_reject(db, channel, member, reason):
    """Reject member awaiting exec approval and send them reason.

    Deletes member from the database.

    Args:
        db: Database object.
        channel: Channel object associated with command invocation.
        member: Member object to reject verification for.
        reason: String representing rejection reason.
    """
    db.update_member_data(member.id, {MemberKey.VER_STATE: None})

    await member.send(
        "Your verification request has been denied "
        f"for the following reason(s): `{reason}`.\n"
        f"You can start a new request by typing `{PREFIX}verify` in the "
        "verification channel."
    )

    await channel.send("Rejected verification request from " f"{member.mention}.")


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_display_pending(db, guild, channel):
    """Display list of members currently awaiting exec approval.

    Args:
        db: Database object.
        guild: Guild object to retrieve member data from.
        channel: Channel object to send list of members to.
    """
    mentions = []
    verifying = db.get_unverified_members_data()
    for member_id in verifying:
        if verifying[member_id][MemberKey.VER_STATE] == State.AWAIT_APPROVAL:
            member = guild.get_member(member_id)
            mentions.append(f"{member.mention}: {member_id}")

    if len(mentions) == 0:
        await channel.send("No members currently awaiting approval.")
        return

    mentions_formatted = "\n".join(mentions)
    await channel.send(f"__Members awaiting approval:__\n{mentions_formatted}")


@pre(check(_awaiting_approval, notify=True))
@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_resend_id(db, channel, member):
    """Resend ID attachments from member to admin channel.

    Admin channel defined in config.

    Retrieves attachments from previous message in admin channel.

    Send error message if previous message was deleted.

    Args:
        db: Database object.
        channel: Channel object associated with command invocation.
        member: Member object to retrieve ID attachments from.
    """
    member_data = db.get_member_data(member.id)
    message_id = member_data[MemberKey.ID_MESSAGE]
    try:
        message = await channel.fetch_message(message_id)
    except NotFound:
        await channel.send(
            "Could not find previous message in this channel "
            "containing attachments! Perhaps it was deleted?"
        )
        return
    attachments = message.attachments

    async with channel.typing():
        files = [await a.to_file() for a in attachments]
        full_name = member_data[MemberKey.NAME]
        await channel.send(
            "Previously received attachment(s) from "
            f"{member.mention}. Please verify that name on ID is "
            f"`{full_name}`, then type `{PREFIX}verify approve {member.id}` "
            f'or `{PREFIX}verify reject {member.id} "reason"`.',
            files=files,
        )


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_verify_manual(
    db, ver_role, channel, join_announce_channel, exec, member, name, arg
):
    """Add member details to database and grant them the verified rank.

    Verified rank defined in config.

    Args:
        db: Database object.
        ver_role: Verified role object to grant to member.
        channel: Channel object to send notifications to.
        join_announce_channel: Channel object to send join announcements to.
        exec: Member object representing verifying exec.
        member: Member object to verify.
        name: String representing member name.
        arg: String representing either zID or email.
    """
    member_data = make_def_member_data()
    member_data.update(
        {
            MemberKey.NAME: name,
            MemberKey.EMAIL_VER: True,
            MemberKey.ID_VER: True,
            MemberKey.VER_EXEC: exec.id,
        }
    )
    if is_valid_zid(arg):
        member_data.update(
            {MemberKey.ZID: arg, MemberKey.EMAIL: f"{arg}@student.unsw.edu.au"}
        )
    elif is_valid_email(arg):
        member_data.update({MemberKey.EMAIL: arg})
    else:
        await channel.send("That is neither a valid zID nor " "a valid email.")
        return
    db.set_member_data(member.id, member_data)
    await proc_grant_rank(ver_role, channel, join_announce_channel, member)


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_rejoin_verified(ver_role, admin_channel, join_announce_channel, member):
    """Regrant previously verified member rank upon rejoining server.

    Verified rank defined in config.

    Args:
        ver_role: Verified role object to grant to member.
        admin_channel: Channel object to send exec notification to.
        member: Member object to grant verified rank to.
    """
    await proc_grant_rank(
        ver_role, admin_channel, join_announce_channel, member, silent=True
    )
    await admin_channel.send(
        f"{member.mention} was previously verified, and "
        "has automatically been granted the verified rank upon (re)joining "
        "the server."
    )


@pre(log_invoke(LOG))
@post(log_success(LOG))
async def proc_grant_rank(
    ver_role, admin_channel, join_announce_channel, member, silent=False
):
    """Grant verified rank to member and notify them and execs.

    Verified rank defined in cofig.

    Args:
        ver_role: Verified role object to grant to member.
        admin_channel: Channel object to send exec notification to.
        join_announce_channel: Channel object to send join announcements to.
        member: Member object to grant verified rank to.
        silent: Boolean representing whether default confirmation messages
            should be sent to member/admin channel.
    """
    await member.add_roles(ver_role)
    LOG.info(f"Granted verified rank to member '{member.id}'")
    if not silent:
        await member.send(
            "You are now verified. Welcome to the server! "
            "If you are interested in subscribing to our newsletter, try the "
            f"`{PREFIX}newsletter` command."
        )
        await admin_channel.send(f"{member.mention} is now verified.")
        await join_announce_channel.send(f"Welcome {member.mention} to PCSoc!")


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

    @property
    def guild(self):
        return self.bot.get_guild(SERVER_ID)

    @property
    def ver_role(self):
        return self.guild.get_role(VERIF_ROLE)

    @property
    def admin_channel(self):
        return self.guild.get_channel(ADMIN_CHANNEL)

    @property
    def join_announce_channel(self):
        return self.guild.get_channel(JOIN_ANNOUNCE_CHANNEL)

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
        ignore_extra=False,
    )
    async def grp_verify(self, ctx):
        """Register verify command group.
        
        Args:
            ctx: Context object associated with command invocation.
        """
        await self.cmd_verify(ctx)

    @pre(log_attempt(LOG))
    @pre(check(in_ver_channel, notify=True))
    @pre(check(is_unverified_user, notify=True))
    @pre(log_invoke(LOG))
    async def cmd_verify(self, ctx):
        """Handle verify command.

        Begin verification process for member that invoked it, if they are not
        already verified.

        Args:
            ctx: Context object associated with command invocation.
        """
        await proc_begin(
            ctx.message, self.db, self.ver_role, self.admin_channel, ctx.author
        )

    @grp_verify.command(
        name="approve",
        help="Verify a member awaiting exec approval.",
        usage="(Discord ID) __member__",
    )
    @pre(log_attempt(LOG))
    @pre(check(in_admin_channel, notify=True))
    @pre(check(is_admin_user, notify=True))
    @pre(log_invoke(LOG))
    @post(log_success(LOG))
    async def cmd_verify_approve(self, ctx, member: Member):
        """Handle verify approve command.

        Grant member verified rank, if they are currently awaiting exec
        approval.

        Args:
            ctx: Context object associated with command invocation.
            member: Associated Member object to approve verification for.
        """
        await proc_exec_approve(
            self.db,
            ctx.channel,
            member,
            self.join_announce_channel,
            ctx.author,
            self.ver_role,
        )

    @grp_verify.command(
        name="reject",
        help="Reject a member awaiting exec approval.",
        usage="(Discord ID) __member__ (multiple words) __reason__",
    )
    @pre(log_attempt(LOG))
    @pre(check(in_admin_channel, notify=True))
    @pre(check(is_admin_user, notify=True))
    @pre(log_invoke(LOG))
    @post(log_success(LOG))
    async def cmd_verify_reject(self, ctx, member: Member, *, reason: str):
        """Handle verify reject command.

        Reject member for verification and delete them from database, if they
        are currently awaiting exec approval.

        Args:
            ctx: Context object associated with command invocation.
            member: Associated Member object to reject verification for.
            reason: Rejection reason.
        """
        await proc_exec_reject(self.db, ctx.channel, member, reason)

    @grp_verify.command(
        name="pending",
        help="Display list of members awaiting approval for verification.",
        usage="",
    )
    @pre(log_attempt(LOG))
    @pre(check(is_admin_user, notify=True))
    @pre(check(in_admin_channel, notify=True))
    @pre(log_invoke(LOG))
    @post(log_success(LOG))
    async def cmd_verify_pending(self, ctx):
        """Handle verify pending command.

        Display list of members currently awaiting exec approval.

        Message will be sent to admin channel defined in config.

        Args:
            ctx: Context object associated with command invocation.
        """
        await proc_display_pending(self.db, self.guild, ctx)

    @grp_verify.command(
        name="check",
        help="Retrieve stored photo of ID from member awaiting approval.",
        usage="(Discord ID) __member__",
    )
    @pre(log_attempt(LOG))
    @pre(check(in_admin_channel, notify=True))
    @pre(check(is_admin_user, notify=True))
    @pre(log_invoke(LOG))
    @post(log_success(LOG))
    async def cmd_verify_check(self, ctx, member_id):
        """Handle verify check command.

        Resend ID attachments from member to admin channel defined in config.

        Args:
            ctx: Context object associated with command invocation.
            member_id: ID of member to retrieve associated ID attachments of.
        """
        member = self.guild.get_member(int(member_id))
        if member is None:
            await ctx.reply("Could not find a member with that ID!")
            return
        await proc_resend_id(self.db, ctx.channel, member)

    @grp_verify.command(
        name="manual",
        help="Manually verify a member with the supplied details.",
        usage="(Discord ID) __member__ (quote) __name__ (word) __zID/Email__",
    )
    @pre(log_attempt(LOG))
    @pre(check(in_admin_channel, notify=True))
    @pre(check(is_admin_user, notify=True))
    @pre(log_invoke(LOG))
    @post(log_success(LOG))
    async def cmd_verify_manual(self, ctx, member_id, name, arg):
        """Handle verify manual command.

        Add member details to database and grant them the verified rank.

        Args:
            ctx: Context object associated with command invocation.
            member_id: ID of member to verify.
            name: String representing member name.
            arg: String representing either zID or email.
        """
        member = self.guild.get_member(int(member_id))
        if member is None:
            await ctx.reply("Could not find a member with that ID!")
            return
        await proc_verify_manual(
            self.db,
            self.ver_role,
            ctx.channel,
            self.join_announce_channel,
            ctx.author,
            member,
            name,
            arg,
        )

    @command(name="restart", hidden=True)
    @pre(log_attempt(LOG))
    @pre(check(in_dm_channel))
    @pre(check(is_guild_member, notify=True))
    @pre(check(is_unverified_user))
    @pre(log_invoke(LOG))
    @post(log_success(LOG))
    async def cmd_restart(self, ctx):
        """Handle restart command.

        Restart verification process for member that invoked it, if they are
        undergoing verification.

        Args:
            ctx: Context object associated with command invocation.
        """
        await proc_restart(self.db, ctx.author)

    @command(name="resend", hidden=True)
    @pre(log_attempt(LOG))
    @pre(check(in_dm_channel))
    @pre(check(is_guild_member, notify=True))
    @pre(check(is_unverified_user))
    @pre(check(is_verifying_user))
    @pre(log_invoke(LOG))
    @post(log_success(LOG))
    async def cmd_resend(self, ctx):
        """Handle resend command.

        Resend verification email to member that invoked it, if they were
        previously sent this email.

        Args:
            ctx: Context object associated with command invocation.
        """
        member_data = self.db.get_member_data(ctx.author.id)
        await proc_resend_email(self.db, self.mail, ctx.author, member_data)

    @Cog.listener()
    @pre(check(is_human, level=None))
    @pre(check(was_verified_user, level=None))
    @pre(log_invoke(LOG, "was verified"))
    @post(log_success(LOG, "was verified"))
    async def on_member_join(self, member):
        """Handle member joining that was previously verified.

        Grant member verified rank.

        Args:
            member: Member object that joined the server.
        """
        await proc_rejoin_verified(
            self.ver_role, self.admin_channel, self.join_announce_channel, member
        )

    @Cog.listener()
    @pre(check(is_human, level=None))
    @pre(check(in_dm_channel, level=None))
    @pre(check(is_not_command, level=None))
    @pre(check(is_guild_member, level=None))
    @pre(check(is_unverified_user, level=None))
    @pre(log_invoke(LOG, meta="verifying"))
    @post(log_success(LOG, meta="verifying"))
    async def on_message(self, message):
        """Handle DM received by unverified member.

        If they are undergoing verification, process message in their FSM.

        Args:
            message: Message object received.
        """
        member = self.guild.get_member(message.author.id)
        await self.proc_handle_state(member, message)

    @pre(log_invoke(LOG))
    @post(log_success(LOG))
    async def proc_handle_state(self, member, message):
        """Call current state handler for member upon receiving message.

        Args:
            member: Member object that sent message.
            message: Message object sent by member.
        """
        try:
            member_data = self.db.get_member_data(member.id)
        except MemberNotFound:
            return
        if not member_data[MemberKey.ID_VER]:
            state = member_data[MemberKey.VER_STATE]
            if state == State.AWAIT_NAME:
                await state_await_name(self.db, member, message.content)
            elif state == State.AWAIT_UNSW:
                await state_await_unsw(self.db, member, message.content)
            elif state == State.AWAIT_ZID:
                await state_await_zid(
                    self.db, self.mail, member, member_data, message.content
                )
            elif state == State.AWAIT_EMAIL:
                await state_await_email(
                    self.db, self.mail, member, member_data, message.content
                )
            elif state == State.AWAIT_CODE:
                await state_await_code(
                    self.db,
                    self.ver_role,
                    self.admin_channel,
                    self.join_announce_channel,
                    member,
                    member_data,
                    message.content,
                )
            elif state == State.AWAIT_ID:
                await state_await_id(
                    self.db,
                    self.admin_channel,
                    member,
                    member_data,
                    message.attachments,
                )
            elif state == State.AWAIT_APPROVAL:
                await state_await_approval()
