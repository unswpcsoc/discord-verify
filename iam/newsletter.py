from requests import get
from discord.ext.commands import Cog, command
from logging import DEBUG, INFO

from iam.db import MemberKey
from iam.log import new_logger
from iam.config import PREFIX, NEWSLETTER_SUB_URL
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
    cog = Newsletter(bot, LOG)
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

async def proc_subscribe(db, user, channel):
    """Subscribe a user to the newsletter using their stored email.

    Args:
        db: Database object.
        user: User object to subscribe.
        channel: Channel to send confirmation message to.
    """
    member_data = db.get_member_data(user.id)
    zid = member_data[MemberKey.ZID]
    get(f"{NEWSLETTER_SUB_URL}"
        f"&FNAME={member_data[MemberKey.NAME].replace(' ', '+')}"
        f"&EMAIL={member_data[MemberKey.EMAIL]}"
        f"&MMERGE2={'No' if zid is None else 'Yes'}"
        f"&MMERGE3={'' if zid is None else zid}")

    await channel.send("Successfully subscribed to the newsletter!")

class Newsletter(Cog, name=COG_NAME):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger

    @property
    def db(self):
        return self.bot.get_cog("Database")

    @command(
        name="newsletter",
        help="Subscribe to our newsletter with your verified email. Note: "
            "there is no unsubscribe command, so you will need to do so via "
            "the link in any of our newsletter emails.",
        usage=""
    )
    @pre(log_attempt(LOG))
    @pre(check(is_strictly_verified_user, notify=True))
    @pre(log_invoke(LOG))
    @post(log_success(LOG))
    async def cmd_newsletter(self, ctx):
        """Handle newsletter command.

        Subscribe a user to the newsletter using their stored email.

        Args:
            ctx: Context object associated with command invocation.
        """
        await proc_subscribe(self.db, ctx.author, ctx.channel)
