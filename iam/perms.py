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

from iam.config import (
    PREFIX, SERVER_ID, VER_ROLE, ALLOW_CHANNELS, ADMIN_CHANNEL, ADMIN_ROLES
)

class CheckFailed(Exception):
    """Method pre-execution check failed.

    Attributes:
        logger: Logger to write debug info to.
        name: String representing name of failed check function.
        ctx: Context object associated with method invocation.
        silent: Boolean for whether to send error message or not in
                default_handle.
        msg: String representing error message to send in invocation context.
    """
    def __init__(self, logger, name, ctx, silent, msg):
        """Init exception with given args.

        Args:
            logger: Logger to write debug info to.
            name: String representing name of failed check function.
            ctx: Context object associated with method invocation.
            silent: Boolean for whether to send error message or not in
                    default_handle.
            msg: String representing error message to send in invocation
                 context.
        """
        self.logger = logger
        self.name = name
        self.ctx = ctx
        self.silent = silent
        self.msg = msg

    async def def_handler(self):
        """Default handler for this exception.
        
        Log a debug message and send msg to ctx if silent == False.
        """
        self.logger.debug(f"User '{self.ctx.author.id}' failed check "
            f"{self.name} in channel '{self.ctx.channel.id}' during command "
            f"invocation: '{self.ctx.message.content}'")
        if not self.silent:
            await self.ctx.send(self.msg)

def check(predicate):
    """Decorate method to only execute if it passes a check.
    
    Check is the function 'predicate'.

    Can only be used with cogs.

    Args:
        predicate: Function that takes in cog and context as args and returns
        boolean value representing result of a check. Need not be async, but
        can be.
    """
    async_predicate = predicate
    if not iscoroutinefunction(predicate):
        @wraps(predicate)
        async def wrapper(cog, ctx):
            return predicate(cog, ctx)
        async_predicate = wrapper

    def decorator(func):
        @wraps(func)
        async def wrapper(cog, ctx, *args):
            if await async_predicate(cog, ctx):
                return await func(cog, ctx, *args)
        return wrapper

    return decorator

def is_verified_user(error=False):
    """Decorate method to only execute if invoker has verified role.
    
    Verified role defined in config.
    
    Cog must have bot as instance variable.

    Args:
        error: Boolean for whether to raise exception if check fails.

    Raises:
        CheckFailed: Check failed and error == True.
    """
    def predicate(cog, ctx):
        member = get_member(cog, ctx.author.id)
        if member is None or VER_ROLE not in get_role_ids(member):
            raise CheckFailed(cog.log, "is_verified_user", ctx, not error,
                "You must be verified to do that.")
        return True
    
    return check(predicate)

def was_verified_user(error=False):
    """Decorate method to only execute if invoker was verified in past.
    
    Verified in past defined as either verified in the database or currently
    has verified rank in Discord.

    Cog must have bot and db as instance variables.

    Args:
        error: Boolean for whether to raise exception if check fails.

    Raises:
        CheckFailed: Check failed and error == True.
    """
    def currently_verified(cog, ctx):
        member = get_member(cog, ctx.author.id)
        if member is None or VER_ROLE not in get_role_ids(member):
            return False
        return True

    def predicate(cog, ctx):
        if currently_verified(cog, ctx):
            return True
        member_info = cog.db.get_member_data(ctx.author.id)
        if member_info == None or not member_info["verified"]:
            raise CheckFailed(cog.log, "was_verified_user", ctx, not error,
                "You must be verified to do that.")
        return True

    return check(predicate)

def is_unverified_user(error=False):
    """Decorate method to only execute if invoker does not have verified role.

    Verified role defined in config.

    Cog must have bot as instance variable.

    Args:
        error: Boolean for whether to raise exception if check fails.

    Raises:
        CheckFailed: Check failed and error == True.
    """
    def predicate(cog, ctx):
        member = get_member(cog, ctx.author.id)
        if member is not None and VER_ROLE in get_role_ids(member):
            raise CheckFailed(cog.log, "is_uverified_user", ctx, not error,
                "You are already verified.")
        return True
    
    return check(predicate)

def never_verified_user(error=False):
    """Decorate method to only execute if invoker was never verified.
    
    Verified defined as being verified in database.

    Cog must have bot and db as instance variables.

    Args:
        error: Boolean for whether to raise exception if check fails.

    Raises:
        CheckFailed: Check failed and error == True.
    """
    def currently_verified(cog, ctx):
        member = get_member(cog, ctx.author.id)
        if member is None or VER_ROLE not in get_role_ids(member):
            return False
        return True

    def predicate(cog, ctx):
        if not currently_verified(cog, ctx):
            member_info = cog.db.get_member_data(ctx.author.id)
            if member_info == None or not member_info["verified"]:
                return True
        raise CheckFailed(cog.log, "never_verified_user", ctx, not error,
            "You are already verified.")

    return check(predicate)

def is_admin_user(error=False):
    """Decorate method to only execute if invoker has at least one admin role.

    Admin roles defined in config
    
    Cog must have bot as instance variable.

    Args:
        error: Boolean for whether to raise exception if check fails.

    Raises:
        CheckFailed: Check failed and error == True.
    """
    def predicate(cog, ctx):
        member = get_member(cog, ctx.author.id)
        if set(ADMIN_ROLES).isdisjoint(get_role_ids(member)):
            raise CheckFailed(cog.log, "is_admin_user", ctx, not error,
                "You are not authorised to do that.")
        return True
    return check(predicate)

def is_guild_member(error=False):
    """Decorate method to only execute if invoked by member of guild.
    
    Guild defined in config.

    Cog must have bot as instance variable.

    Args:
        error: Boolean for whether to raise exception if check fails.

    Raises:
        CheckFailed: Check failed and error == True.
    """
    def predicate(cog, ctx):
        if get_member(cog, ctx.author.id) is None:
            raise CheckFailed(cog.log, "is_guild_member", ctx, not error,
                "You must be a member of the server to do that.")
        return True
    return check(predicate)

def in_allowed_channel(error=False):
    """Decorate method to only execute if invoked in an allowed channel.
    
    Allowed channels defined in config.

    Args:
        error: Boolean for whether to raise exception if check fails.

    Raises:
        CheckFailed: Check failed and error == True.
    """
    def predicate(cog, ctx):
        if ctx.channel.id not in ALLOW_CHANNELS:
            raise CheckFailed(cog.log, "in_allowed_channel", ctx, not error,
                "You cannot do that in this channel.")
        return True
    return check(predicate)

def in_admin_channel(error=False):
    """Decorate method to only execute if invoked in admin channel.
    
    Admin channel defined in config.

    Args:
        error: Boolean for whether to raise exception if check fails.

    Raises:
        CheckFailed: Check failed and error == True.
    """
    def predicate(cog, ctx):
        if ctx.channel.id != ADMIN_CHANNEL:
            raise CheckFailed(cog.log, "in_admin_channel", ctx, not error,
                "You must be in the admin channel to do that.")
        return True
    return check(predicate)

def in_dm_channel(error=False):
    """Decorate method to only execute if invoked in DM channel.

    Args:
        error: Boolean for whether to raise exception if check fails.

    Raises:
        CheckFailed: Check failed and error == True.
    """
    def predicate(cog, ctx):
        if ctx.guild is not None:
            raise CheckFailed(cog.log, "in_dm_channel", ctx, not error,
                "You must be in a DM channel to do that.")
        return True
    return check(predicate)

def is_human():
    """Decorate method to only execute if invoked by human.
    
    Prevents bot from handling events triggered by bots, including itself.
    """
    def predicate(cog, ctx):
        if ctx.author.bot:
            return False
        return True
    return check(predicate)

def is_not_command():
    """Decorate method to only execute if not command.

    Prevents bot from handling on_message events generated by commands.

    Commands defined as starting with command prefix defined in config.
    """
    def predicate(cog, ctx):
        if ctx.content.startswith(PREFIX):
            return False
        return True
    return check(predicate)

def get_member(cog, id):
    """Get member with given Discord ID.
    
    Args:
        cog: Cog that invoked this function. Must have bot as instance
             variable.
        id: Discord ID of member.

    Returns:
        The Member object associated with id and the guild defined in the
        config.
    """
    return cog.bot.get_guild(SERVER_ID).get_member(id)

def get_role_ids(member):
    """Get list of IDs of all roles member has.

    Args:
        member: Member object.

    Returns:
        List of IDs of all roles member has.
    """
    return [r.id for r in member.roles]
