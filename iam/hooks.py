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

def pre(action, log_check=True, error=False):
    """Decorate method to execute a function before itself.

    Args:
        action: Function to execute. Takes in the following args:
            mtd: Method being invoked.
            cls: Class associated with method.
            *args: Arguments supplied to method call.
        log_check: Boolean for whether to log CheckFailed.
        error: Boolean for whether to propagate CheckFailed.

    Raises:
        Propagates CheckFailed if error == True.
    """
    def decorator(mtd):
        @wraps(mtd)
        async def wrapper(cls, *args):
            try:
                await make_coro(action)(mtd, cls, *args)
            except CheckFailed as err:
                if log_check:
                    log_event(cls, args[0], f"{mtd.__name__}: failed check " 
                        f"'{action.__name__}'")
                if error:
                    raise err
                return
            await mtd(cls, *args)
        return wrapper
    return decorator

def post(action, log_check=True, error=False):
    """Decorate method to execute a function after itself.

    Args:
        action: Function to execute. Takes in the following args:
            mtd: Method being invoked.
            cls: Class associated with method.
            *args: Arguments supplied to method call.
        log_check: Boolean for whether to log CheckFailed.
        error: Boolean for whether to propagate CheckFailed.

    Raises:
        Propagates CheckFailed if error == True.
    """
    def decorator(mtd):
        @wraps(mtd)
        async def wrapper(cls, *args):
            await mtd(cls, *args)
            try:
                await make_coro(action)(mtd, cls, *args)
            except CheckFailed as err:
                if log_check:
                    log_event(cls, args[0], f"{mtd.__name__}: failed check " 
                        f"'{action.__name__}'")
                if error:
                    raise err
                return
        return wrapper
    return decorator

def log(meta="", level=DEBUG):
    """Log function call.

    Args:
        func: Function called.
        cog: Cog associated with function call.
        ctx: Context object associated with function call. Associated cog must
             have log as an instance variable.
    """
    def wrapper(func, cog, ctx, *_):
        info = [func.__name__, meta]
        log_event(cog, ctx, ": ".join(filter(None, info)), level)
    return wrapper

def log_attempt(meta="", level=DEBUG):
    """Log function invoke attempt.

    Args:
        meta: String representing info about function.
        level: Logging level to log at.
    """
    info = ["invoke attempt", meta]
    return log(meta=" - ".join(filter(None, info)), level=level)

def log_invoke(meta="", level=INFO):
    """Log function invoke success.

    Args:
        meta: String representing info about function.
        level: Logging level to log at.
    """
    info = ["invoke success", meta]
    return log(meta=" - ".join(filter(None, info)), level=level)

def log_success(meta="", level=DEBUG):
    """Log function execute success.

    Args:
        meta: String representing info about function.
        level: Logging level to log at.
    """
    info = ["execute success", meta]
    return log(meta=" - ".join(filter(None, info)), level=level)

def is_verified_user(func, cog, object, *_):
    """Raises exception if invoker does not have verified role.
    
    Verified role defined in config.
    
    Associated cog must have bot as instance variable.

    Args:
        func: Function invoked.
        cog: Cog assicated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoker does not have verified role.
    """
    member = get_member(cog.bot, object.author)
    if member is None or VER_ROLE not in get_role_ids(member):
        raise CheckFailed(object, "You must be verified to do that.")

def was_verified_user(func, cog, object, *_):
    """Raises exception if invoker was never verified in past.
    
    Verified in past defined as either verified in the database or currently
    has verified rank (defined in config) in Discord.

    Associated cog must have bot and db as instance variables.

    Args:
        func: Function invoked.
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

def is_unverified_user(func, cog, object, *_):
    """Raises exception if invoker has verified role.

    Verified role defined in config.

    Associated cog must have bot as instance variable.

    Args:
        func: Function invoked.
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoker has verified role.
    """
    member = get_member(cog.bot, object.author)
    if member is not None and VER_ROLE in get_role_ids(member):
        raise CheckFailed(object, "You are already verified.")

def never_verified_user(func, cog, object, *_):
    """Raise exception if invoker was verified in past.
    
    Verified in past defined as either verified in the database or currently
    has verified rank (defined in config) in Discord.

    Associated cog must have bot and db as instance variables.

    Args:
        func: Function invoked.
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

def is_admin_user(func, cog, object, *_):
    """Raise exception if invoker does not have at least one admin role.

    Admin roles defined in config.
    
    Associated cog must have bot as instance variable.

    Args:
        func: Function invoked.
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoker does not have at least one admin role.
    """
    member = get_member(cog.bot, object.author)
    if set(ADMIN_ROLES).isdisjoint(get_role_ids(member)):
        raise CheckFailed(object, "You are not authorised to do that.")

def is_guild_member(func, cog, object, *_):
    """Raise exception if invoker is not member of guild.
    
    Guild defined in config.

    Associated cog must have bot as instance variable.

    Args:
        func: Function invoked.
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoker is not member of guild.
    """
    if get_member(cog.bot, object.author) is None:
        raise CheckFailed(object, "You must be a member of the server "
            "to do that.")

def in_allowed_channel(func, cog, object, *_):
    """Raise exception if not invoked in an allowed channel.
    
    Allowed channels defined in config.

    Args:
        func: Function invoked.
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If not invoked in an allowed channel.
    """
    if object.channel.id not in ALLOW_CHANNELS:
        raise CheckFailed(object, "You cannot do that in this channel.")

def in_admin_channel(func, cog, object, *_):
    """Raise exception if not invoked in admin channel.
    
    Admin channel defined in config.

    Args:
        func: Function invoked.
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If not invoked in admin channel.
    """
    if object.channel.id != ADMIN_CHANNEL:
        raise CheckFailed(object, "You must be in the admin channel to do that.")

def in_dm_channel(func, cog, object, *_):
    """Raise exception if not invoked in DM channel.

    Args:
        func: Function invoked.
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If not invoked in DM channel.
    """
    if object.guild is not None:
        raise CheckFailed(object, "You must be in a DM channel to do that.")

def is_human(func, cog, object, *_):
    """Raise exception if invoked by bot.
    
    Prevents bot from handling events triggered by bots, including itself.

    Args:
        func: Function invoked.
        cog: Cog associated with command invocation.
        object: Object associated with command invocation.

    Raises:
        CheckFailed: If invoked by bot.
    """
    if object.author.bot:
        raise CheckFailed(object, "You are not human.")

def is_not_command(func, cog, message, *_):
    """Raise exception if message is not command.

    Prevents bot from handling on_message events generated by commands.

    Commands defined as starting with command prefix defined in config.

    Args:
        func: Function invoked.
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
