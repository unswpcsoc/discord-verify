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

"""Handle command permissions."""

from functools import wraps
from inspect import iscoroutinefunction
from discord import Message

from iam.config import (
    PREFIX, SERVER_ID, VER_ROLE, ALLOW_CHANNELS, ADMIN_CHANNEL, ADMIN_ROLES
)

class CheckFailed(Exception):
    """Method pre-execution check failed.

    Attributes:
        ctx: Context object associated with method invocation.
        msg: String representing error message to send in invocation context.
    """
    def __init__(self, ctx, msg):
        """Init exception with given args.

        Args:
            ctx: Context object associated with method invocation.
            msg: String representing error message to send in invocation
                 context.
        """
        self.ctx = ctx
        self.msg = msg

    async def def_handler(self):
        """Default handler for this exception.
        
        Send msg to ctx if silent == False.
        """
        await self.ctx.send(self.msg)

def make_coro(func):
    """Turns a function into a coroutine without modifying its behaviour.

    Args:
        func: The function to convert.

    Returns:
        Coroutine of given function, or original function if already async.
    """
    if not iscoroutinefunction(func):
        @wraps(func)
        async def wrapper(*args):
            return func(*args)
        return wrapper
    return func

def pre(action, error=False):
    """Decorate method to execute a function before itself.

    Can only be used with cogs.

    Args:
        action: Function to execute. Takes in ctx as an arg.
        error: Boolean for whether to propagate CheckFailed.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(cog, ctx, *args):
            try:
                await make_coro(action)(ctx)
            except CheckFailed as err:
                if not isinstance(ctx, Message):
                    cog.log.debug(f"User '{ctx.author.id}' failed check "
                        f"{action.__name__} in channel '{ctx.channel.id}' "
                        f"during command invocation: '{ctx.message.content}'")
                    if error:
                        raise err
                return
            await func(cog, ctx, *args)
        return wrapper
    return decorator

def post(action, error=False):
    """Decorate method to execute a function after itself.

    Can only be used with cogs.

    Args:
        action: Function to execute. Takes in ctx as an arg.
        error: Boolean for whether to propagate CheckFailed.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(cog, ctx, *args):
            await func(cog, ctx, *args)
            try:
                await make_coro(action)(ctx)
            except CheckFailed as err:
                cog.log.debug(f"User '{ctx.author.id}' failed check "
                    f"{action.__name__} in channel '{ctx.channel.id}' "
                    f"during command invocation: '{ctx.message.content}'")
                if error:
                    raise err
        return wrapper
    return decorator

def log_cmd_attempt(ctx):
    """Logs a command invoke attempt.

    Args:
        ctx: Context object associated with command invocation. Associated cog
             must have log as an instance variable.
    """
    ctx.cog.log.debug(f"Attempted command invoke '{ctx.message.content}' "
        f"by user '{ctx.author.id}'")

def log_cmd_success(ctx):
    """Logs a successful command invoke.

    Args:
        ctx: Context object associated with command invocation. Associated cog
             must have log as an instance variable.
    """
    ctx.cog.log.info(f"Successful command invoke '{ctx.message.content}' "
        f"by user '{ctx.author.id}'")

def is_verified_user(ctx):
    """Raises exception if invoker does not have verified role.
    
    Verified role defined in config.
    
    Associated cog must have bot as instance variable.

    Args:
        ctx: Context object.

    Raises:
        CheckFailed: If invoker does not have verified role.
    """
    member = get_member(ctx)
    if member is None or VER_ROLE not in get_role_ids(member):
        raise CheckFailed(ctx, "You must be verified to do that.")

def was_verified_user(ctx):
    """Raises exception if invoker was never verified in past.
    
    Verified in past defined as either verified in the database or currently
    has verified rank (defined in config) in Discord.

    Associated cog must have bot and db as instance variables.

    Args:
        ctx: Context object.

    Raises:
        CheckFailed: If invoker was never verified in past.
    """
    member = get_member(ctx)
    if member is not None and VER_ROLE in get_role_ids(member):
        return
    member_info = ctx.cog.db.get_member_data(ctx.author.id)
    if member_info == None or not member_info["verified"]:
        raise CheckFailed(ctx, "You must be verified to do that.")

def is_unverified_user(ctx):
    """Raises exception if invoker has verified role.

    Verified role defined in config.

    Associated cog must have bot as instance variable.

    Args:
        ctx: Context object.

    Raises:
        CheckFailed: If invoker has verified role.
    """
    member = get_member(ctx)
    if member is not None and VER_ROLE in get_role_ids(member):
        raise CheckFailed(ctx, "You are already verified.")

def never_verified_user(ctx):
    """Raise exception if invoker was verified in past.
    
    Verified in past defined as either verified in the database or currently
    has verified rank (defined in config) in Discord.

    Associated cog must have bot and db as instance variables.

    Args:
        ctx: Context object.

    Raises:
        CheckFailed: If invoker was verified in past.
    """
    member = get_member(ctx)
    if member is None or VER_ROLE not in get_role_ids(member):
        member_info = ctx.cog.db.get_member_data(ctx.author.id)
        if member_info == None or not member_info["verified"]:
            return True
    raise CheckFailed(ctx, "You are already verified.")

def is_admin_user(ctx):
    """Raise exception if invoker does not have at least one admin role.

    Admin roles defined in config.
    
    Associated cog must have bot as instance variable.

    Args:
        ctx: Context object.

    Raises:
        CheckFailed: If invoker does not have at least one admin role.
    """
    member = get_member(ctx)
    if set(ADMIN_ROLES).isdisjoint(get_role_ids(member)):
        raise CheckFailed(ctx, "You are not authorised to do that.")

def is_guild_member(ctx):
    """Raise exception if invoker is not member of guild.
    
    Guild defined in config.

    Associated cog must have bot as instance variable.

    Args:
        ctx: Context object.

    Raises:
        CheckFailed: If invoker is not member of guild.
    """
    if get_member(ctx) is None:
        raise CheckFailed(ctx, "You must be a member of the server "
            "to do that.")

def in_allowed_channel(ctx):
    """Raise exception if not invoked in an allowed channel.
    
    Allowed channels defined in config.

    Args:
        ctx: Context object.

    Raises:
        CheckFailed: If not invoked in an allowed channel.
    """
    if ctx.channel.id not in ALLOW_CHANNELS:
        raise CheckFailed(ctx, "You cannot do that in this channel.")

def in_admin_channel(ctx):
    """Raise exception if not invoked in admin channel.
    
    Admin channel defined in config.

    Args:
        ctx: Context object.

    Raises:
        CheckFailed: If not invoked in admin channel.
    """
    if ctx.channel.id != ADMIN_CHANNEL:
        raise CheckFailed(ctx, "You must be in the admin channel to do that.")

def in_dm_channel(ctx):
    """Raise exception if not invoked in DM channel.

    Args:
        ctx: Context object.

    Raises:
        CheckFailed: If not invoked in DM channel.
    """
    if ctx.guild is not None:
        raise CheckFailed(ctx, "You must be in a DM channel to do that.")

def is_human(ctx):
    """Raise exception if invoked by bot.
    
    Prevents bot from handling events triggered by bots, including itself.

    Args:
        ctx: Context object.

    Raises:
        CheckFailed: If invoked by bot.
    """
    if ctx.author.bot:
        raise CheckFailed(ctx, "You are not human.")

def is_not_command(ctx):
    """Raise exception if message is not command.

    Prevents bot from handling on_message events generated by commands.

    Commands defined as starting with command prefix defined in config.

    Args:
        ctx: Context object.

    Raises:
        CheckFailed: If message is not command.
    """
    if ctx.content.startswith(PREFIX):
        raise CheckFailed(ctx, "That is not a command.")

def get_member(ctx):
    """Get member associated with context.
    
    Args:
        ctx: Context object.

    Returns:
        The Member object associated with given context.
    """
    return ctx.cog.bot.get_guild(SERVER_ID).get_member(ctx.author.id)

def get_role_ids(member):
    """Get list of IDs of all roles member has.

    Args:
        member: Member object.

    Returns:
        List of IDs of all roles member has.
    """
    return [r.id for r in member.roles]
