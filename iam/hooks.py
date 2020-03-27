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

from logging import DEBUG, INFO
from functools import wraps
from inspect import iscoroutinefunction
from discord.ext.commands import Context

from iam.log import log_event
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
        async def wrapper(cog, *args):
            try:
                await make_coro(action)(cog, *args)
            except CheckFailed as err:
                if isinstance(args[0], Context):
                    log_event(cog, args[0], DEBUG, "failed check "
                        f"{action.__name__}")
                    if error:
                        raise err
                return
            await func(cog, *args)
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
        async def wrapper(cog, *args):
            await func(cog, *args)
            try:
                await make_coro(action)(cog, *args)
            except CheckFailed as err:
                if isinstance(args[0], Context):
                    log_event(cog, args[0], DEBUG, "failed check "
                        f"{action.__name__}")
                    if error:
                        raise err
                return
        return wrapper
    return decorator

def log_cmd_attempt(cog, ctx, *_):
    """Logs a command invoke attempt.

    Args:
        cog: Cog associated with command invocation.
        ctx: Context object associated with command invocation. Associated cog
             must have log as an instance variable.
    """
    log_event(cog, ctx, DEBUG, "attempt command invoke")

def log_cmd_invoke(cog, ctx, *_):
    """Logs a command invoke.

    Args:
        cog: Cog associated with command invocation.
        ctx: Context object associated with command invocation. Associated cog
             must have log as an instance variable.
    """
    log_event(cog, ctx, INFO, "command invoke")

def log_cmd_success(cog, ctx, *_):
    """Logs a successful command handler execution.

    Args:
        cog: Cog associated with command invocation.
        ctx: Context object associated with command invocation. Associated cog
             must have log as an instance variable.
    """
    log_event(cog, ctx, DEBUG, "successful command execution")

def log_on_msg_invoke(meta):
    """Logs an on_message invoke.

    Args:
        meta: String representing info about handler attached to this event.
    """
    def wrapper(cog, message, *_):
        log_event(cog, message, INFO, f"on_message invoke: '{meta}'")
    return wrapper

def log_on_msg_success(meta):
    """Logs a successful on_message handler execution.

    Args:
        meta: String representing info about handler attached to this event.
    """
    def wrapper(cog, message, *_):
        log_event(cog, message, DEBUG, f"successful on_message execution: "
            f"'{meta}'")
    return wrapper

def log_on_mem_join_invoke(meta):
    """Logs an on_member_join invoke.

    Args:
        meta: String representing info about handler attached to this event.
    """
    def wrapper(cog, member, *_):
        log_event(cog, member, INFO, f"on_member_join invoke: '{meta}'")
    return wrapper

def log_on_mem_join_success(meta):
    """Logs a successful on_member_join handler execution.

    Args:
        meta: String representing info about handler attached to this event.
    """
    def wrapper(cog, member, *_):
        log_event(cog, member, DEBUG, f"successful on_member_join execution: "
            f"'{meta}'")
    return wrapper

def is_verified_user(cog, object, *_):
    """Raises exception if invoker does not have verified role.
    
    Verified role defined in config.
    
    Associated cog must have bot as instance variable.

    Args:
        cog: Cog assicated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoker does not have verified role.
    """
    member = get_member(cog.bot, object.author)
    if member is None or VER_ROLE not in get_role_ids(member):
        raise CheckFailed(object, "You must be verified to do that.")

def was_verified_user(cog, object, *_):
    """Raises exception if invoker was never verified in past.
    
    Verified in past defined as either verified in the database or currently
    has verified rank (defined in config) in Discord.

    Associated cog must have bot and db as instance variables.

    Args:
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoker was never verified in past.
    """
    member = get_member(cog.bot, object.author)
    if member is not None and VER_ROLE in get_role_ids(member):
        return
    member_info = cog.db.get_member_data(object.author.id)
    if member_info == None or not member_info["verified"]:
        raise CheckFailed(object, "You must be verified to do that.")

def is_unverified_user(cog, object, *_):
    """Raises exception if invoker has verified role.

    Verified role defined in config.

    Associated cog must have bot as instance variable.

    Args:
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoker has verified role.
    """
    member = get_member(cog.bot, object.author)
    if member is not None and VER_ROLE in get_role_ids(member):
        raise CheckFailed(object, "You are already verified.")

def never_verified_user(cog, object, *_):
    """Raise exception if invoker was verified in past.
    
    Verified in past defined as either verified in the database or currently
    has verified rank (defined in config) in Discord.

    Associated cog must have bot and db as instance variables.

    Args:
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoker was verified in past.
    """
    member = get_member(cog.bot, object.author)
    if member is None or VER_ROLE not in get_role_ids(member):
        member_info = cog.db.get_member_data(object.author.id)
        if member_info == None or not member_info["verified"]:
            return True
    raise CheckFailed(object, "You are already verified.")

def is_admin_user(cog, object, *_):
    """Raise exception if invoker does not have at least one admin role.

    Admin roles defined in config.
    
    Associated cog must have bot as instance variable.

    Args:
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoker does not have at least one admin role.
    """
    member = get_member(cog.bot, object.author)
    if set(ADMIN_ROLES).isdisjoint(get_role_ids(member)):
        raise CheckFailed(object, "You are not authorised to do that.")

def is_guild_member(cog, object, *_):
    """Raise exception if invoker is not member of guild.
    
    Guild defined in config.

    Associated cog must have bot as instance variable.

    Args:
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoker is not member of guild.
    """
    if get_member(cog.bot, object.author) is None:
        raise CheckFailed(object, "You must be a member of the server "
            "to do that.")

def in_allowed_channel(cog, object, *_):
    """Raise exception if not invoked in an allowed channel.
    
    Allowed channels defined in config.

    Args:
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If not invoked in an allowed channel.
    """
    if object.channel.id not in ALLOW_CHANNELS:
        raise CheckFailed(object, "You cannot do that in this channel.")

def in_admin_channel(cog, object, *_):
    """Raise exception if not invoked in admin channel.
    
    Admin channel defined in config.

    Args:
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If not invoked in admin channel.
    """
    if object.channel.id != ADMIN_CHANNEL:
        raise CheckFailed(object, "You must be in the admin channel to do that.")

def in_dm_channel(cog, object, *_):
    """Raise exception if not invoked in DM channel.

    Args:
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If not invoked in DM channel.
    """
    if object.guild is not None:
        raise CheckFailed(object, "You must be in a DM channel to do that.")

def is_human(cog, object, *_):
    """Raise exception if invoked by bot.
    
    Prevents bot from handling events triggered by bots, including itself.

    Args:
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoked by bot.
    """
    if object.author.bot:
        raise CheckFailed(object, "You are not human.")

def is_not_command(cog, message, *_):
    """Raise exception if message is not command.

    Prevents bot from handling on_message events generated by commands.

    Commands defined as starting with command prefix defined in config.

    Args:
        cog: Cog associated with event.
        message: Message object associated with event.

    Raises:
        CheckFailed: If message is not command.
    """
    if message.content.startswith(PREFIX):
        raise CheckFailed(message, "That is not a command.")

def get_member(bot, user):
    """Get member of guild given User object.
    
    Guild defined in config.

    Args:
        bot: Bot object, must be member of guild.
        user: User object to search for.

    Returns:
        The Member object associated with given context.
    """
    return bot.get_guild(SERVER_ID).get_member(user.id)

def get_role_ids(member):
    """Get list of IDs of all roles member has.

    Args:
        member: Member object.

    Returns:
        List of IDs of all roles member has.
    """
    return [r.id for r in member.roles]
