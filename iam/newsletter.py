"""Handle newsletter subscriptions for users."""

from mailchimp_marketing import Client
from mailchimp_marketing.api_client import ApiClientError
from hashlib import md5
from discord.ext.commands import Cog, group
from logging import DEBUG, INFO

from iam.db import MemberKey
from iam.log import new_logger
from iam.config import PREFIX, MAILCHIMP_API_KEY, MAILCHIMP_LIST_ID
from iam.hooks import (
    pre, post, check, log_attempt, log_invoke, log_success,
    is_strictly_verified_user
)

LOG = new_logger(__name__)
"""Logger for this module."""

COG_NAME = "Newsletter"
"""Name of this module's Cog."""

def setup(bot):
    """Add Newsletter cog to bot and set up logging.

    Args:
        bot: Bot object to add cog to.
    """
    LOG.debug(f"Setting up {__name__} extension...")
    cog = Newsletter(bot, MAILCHIMP_API_KEY, MAILCHIMP_LIST_ID, LOG)
    LOG.debug(f"Initialised {COG_NAME} cog")
    bot.add_cog(cog)
    LOG.debug(f"Added {COG_NAME} cog to bot")

def teardown(bot):
    """Remove Newsletter cog from bot and remove logging.

    Args:
        bot: Bot object to remove cog from.
    """
    LOG.debug(f"Tearing down {__name__} extension...")
    bot.remove_cog(COG_NAME)
    LOG.debug(f"Removed {COG_NAME} cog from bot")
    for handler in LOG.handlers:
        LOG.removeHandler(handler)

class SubscriptionError(Exception):
    """Error occurred while modifying newsletter subscription.
    
    Attributes:
        channel: Channel object to send error to on notify.
        user: User object associated with event invocation.
        msg: String representing error message to send in invocation context.
    """
    def __init__(self, channel, user, msg, error):
        """Init exception with given args.

        Args:
            channel: Channel object to send error to on notify.
            user: User object associated with event invocation.
            msg: String representing error message to send in invocation
                 context.
        """
        self.channel = channel
        self.user = user
        self.msg = msg
        self.error = error

    async def notify(self):
        """Default handler for this exception.
        
        Log error and send msg to channel.
        """
        LOG.error("Failed to modify newsletter subscription of member "
            f"'{self.user}'. Error given: '{self.error}'")
        await self.channel.send(self.msg)

def subscriber_hash(email):
    """Return the subscriber hash for a given email.

    Args:
        email: String representing email.

    Returns:
        String representing subscriber hash.
    """
    return md5(email.lower().encode()).hexdigest()

async def proc_subscribe(client, list_id, db, user, channel):
    """Subscribe a user to the newsletter using their stored email.

    Args:
        client: Mailchimp Client object.
        list_id: String representing Mailchimp list ID.
        db: Database object.
        user: User object to subscribe.
        channel: Channel to send confirmation message to.
    """
    member_data = db.get_member_data(user.id)
    email = member_data[MemberKey.EMAIL]
    zid = member_data[MemberKey.ZID]
    try:
        res = client.lists.set_list_member(list_id, subscriber_hash(email), {
            "email_address": email,
            "status_if_new": "subscribed",
            "status": "subscribed",
            "merge_fields": {
                "FNAME": member_data[MemberKey.NAME],
                "MMERGE2": "No" if zid is None else "Yes",
                "MMERGE3": "" if zid is None else zid
            }
        })
    except ApiClientError as e:
        raise SubscriptionError(channel, user, "Oops! Something went wrong "
            "while attempting to subscribe you to the newsletter. Please "
            "contact an admin.", e.text)

    await channel.send("Successfully subscribed to the newsletter!")

async def proc_unsubscribe(client, list_id, db, user, channel):
    """Unsubscribe a user to the newsletter using their stored email.

    Deletes user's entry from Mailchimp entirely.

    Args:
        client: Mailchimp Client object.
        list_id: String representing Mailchimp list ID.
        db: Database object.
        user: User object to unsubscribe.
        channel: Channel to send confirmation message to.
    """
    member_data = db.get_member_data(user.id)
    email = member_data[MemberKey.EMAIL]
    zid = member_data[MemberKey.ZID]
    try:
        res = client.lists.set_list_member(list_id, subscriber_hash(email), {
            "email_address": email,
            "status_if_new": "unsubscribed",
            "status": "unsubscribed",
            "merge_fields": {
                "FNAME": member_data[MemberKey.NAME],
                "MMERGE2": "No" if zid is None else "Yes",
                "MMERGE3": "" if zid is None else zid
            }
        })
    except ApiClientError as e:
        raise SubscriptionError(channel, user, "Oops! Something went wrong "
            "while attempting to unsubscribe you from the newsletter. Please "
            "contact an admin.", e.text)

    await channel.send("Successfully unsubscribed from the newsletter!")

class Newsletter(Cog, name=COG_NAME):
    """Handle newsletter subscriptions for users.

    Attributes:
        bot: Bot object that registered this cog.
        db: Database cog associated with bot.
        logger: Logger for this cog.
        client: Mailchimp Client object.
        list_id: String representing Mailchimp list ID.
    """
    def __init__(self, bot, api_key, list_id, logger):
        """Init cog and connect to Mailchimp.

        Args:
            bot: Bot object that registered this cog.
            api_key: String representing Mailchimp API key.
            list_id: String representing Mailchimp list ID.
            logger: Logger for this cog.
        """
        self.bot = bot
        self.client = client = Client({"api_key": api_key})
        self.list_id = list_id
        self.logger = logger

    @property
    def db(self):
        return self.bot.get_cog("Database")

    @group(
        name="newsletter",
        help="Newsletter subscription related commands.",
        usage="",
        invoke_without_command=True,
        ignore_extra=False
    )
    async def grp_newsletter(self, ctx):
        """Register newsletter command group.
        
        Args:
            ctx: Context object associated with command invocation.
        """
        pass

    @grp_newsletter.command(
        name="sub",
        help="Subscribe to our newsletter with your verified email.",
        usage=""
    )
    @pre(log_attempt(LOG))
    @pre(check(is_strictly_verified_user, notify=True))
    @pre(log_invoke(LOG))
    @post(log_success(LOG))
    async def cmd_newsletter_sub(self, ctx):
        """Handle newsletter sub command.

        Subscribe a user to the newsletter using their stored email.

        Args:
            ctx: Context object associated with command invocation.
        """
        await proc_subscribe(self.client, self.list_id, self.db, ctx.author,
            ctx.channel)

    @grp_newsletter.command(
        name="unsub",
        help="Unsubscribe from our newsletter with your verified email.",
        usage=""
    )
    @pre(log_attempt(LOG))
    @pre(check(is_strictly_verified_user, notify=True))
    @pre(log_invoke(LOG))
    @post(log_success(LOG))
    async def cmd_newsletter_unsub(self, ctx):
        """Handle newsletter unsub command.

        Unsubscribe a user from the newsletter using their stored email.

        Args:
            ctx: Context object associated with command invocation.
        """
        await proc_unsubscribe(self.client, self.list_id, self.db, ctx.author,
            ctx.channel)
