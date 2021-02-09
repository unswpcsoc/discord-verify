"""Handle command permissions."""

from logging import DEBUG, INFO
from functools import wraps
from inspect import iscoroutinefunction
from discord import User, Member
from discord.ext.commands import Context

from iam.db import MemberKey, MemberNotFound
from iam.log import log_func
from iam.config import (
    PREFIX, SERVER_ID, VERIF_ROLE, VER_CHANNEL, ADMIN_CHANNEL, ADMIN_ROLES
)

class CheckFailed(Exception):
    """Event pre-execution check failed.

    Attributes:
        obj: Object to send error to on notify.
        msg: String representing error message to send on notify.
    """
    def __init__(self, obj, msg):
        """Init exception with given args.

        Args:
            obj: Context to send error to on notify.
            msg: String representing error message to send on notify.
        """
        self.obj = obj
        self.msg = msg

    async def notify(self):
        """Default handler for this exception.
        
        Send msg to ctx if silent == False.
        """
        await self.obj.reply(self.msg)

class CheckResult:
    """Store boolean, message result of a check.

    Attributes:
        status: Boolean representing result of check.
        msg: String containing info message from check result.
    """
    def __init__(self, status, msg):
        """Init with given args.
        
        Attributes:
            status: Boolean representing result of check.
            msg: String containing info message from check result.
        """
        self.status = status
        self.msg = msg

def make_coro(func):
    """Turns a function into a coroutine without modifying its behaviour.

    Args:
        func: The function to convert.

    Returns:
        Coroutine of given function, or original function if already async.
    """
    if not iscoroutinefunction(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return func

def pre(action):
    """Decorate function to execute a function before itself.

    Args:
        action: Function to execute. Takes in the following args:
            func: Function being invoked.
            *args: Args supplied to function call.
            **kwargs: Keyword args supplied to function call.
    """
    def decorator(func):
        if iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if await make_coro(action)(func, *args, **kwargs):
                    return await func(*args, **kwargs)
        else:
            @wraps(func)
            def wrapper(*args, **kwargs):
                if action(func, *args, **kwargs):
                    return func(*args, **kwargs)
        return wrapper
    return decorator
    
def post(action):
    """Decorate function to execute a function after itself.

    Args:
        action: Function to execute. Takes in the following args:
            func: Function being invoked.
            *args: Args supplied to function call.
            **kwargs: Keyword args supplied to function call.
    """
    def decorator(func):
        if iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                ret_val = await func(*args, **kwargs)
                if await make_coro(action)(func, *args, **kwargs):
                    return ret_val
        else:
            @wraps(func)
            def wrapper(*args, **kwargs):
                ret_val = func(*args, **kwargs)
                if action(func, *args, **kwargs):
                    return ret_val
        return wrapper
    return decorator

def log(logger, meta="", level=DEBUG):
    """Log function call.

    Args:
        meta: String representing info about function.
        level: Logging level to log at.
    """
    def wrapper(func, *args, **kwargs):
        info = [func.__name__, meta]
        log_func(logger, level, ": ".join(filter(None, info)), *args, **kwargs)
        return True
    return wrapper

def log_attempt(logger, meta="", level=DEBUG):
    """Log function invoke attempt.

    Args:
        logger: Logger to write log to.
        meta: String representing info about function.
        level: Logging level to log at.
    """
    info = ["invoke attempt", meta]
    return log(logger, meta=" - ".join(filter(None, info)), level=level)

def log_invoke(logger, meta="", level=INFO):
    """Log function invoke success.

    Args:
        logger: Logger to write log to.
        meta: String representing info about function.
        level: Logging level to log at.
    """
    info = ["invoke success", meta]
    return log(logger, meta=" - ".join(filter(None, info)), level=level)

def log_success(logger, meta="", level=DEBUG):
    """Log function execute success.

    Args:
        logger: Logger to write log to.
        meta: String representing info about function.
        level: Logging level to log at.
    """
    info = ["execute success", meta]
    return log(logger, meta=" - ".join(filter(None, info)), level=level)

def check(check_func, level=DEBUG, notify=False):
    """Performs check on function call to determine if it should proceed.

    For use with the pre and post decorators.

    Args:
        check_func: A function that takes in the args/kwargs supplied to the
                    function being invoked, performs a check and returns:
                        1. If the invocation should proceed.
                        2. Error message to supply, if check failed.
        level: Logging level to write log at if check fails. If this is None,
               will not write log.
        notify: Boolean representing whether to send error message to
                invocation context if check fails.        

    Returns:
        An "action" function usable with the pre and post decorators.
    """
    async def action(func, cog, obj, *args, **kwargs):
        """Performs check on function call to determine if it should proceed.
        
        Args:
            func: Function being invoked.
            cog: Cog associated with function invocation.
            obj: Object associated with function invocation.

        Returns:
            Boolean result of check.
        """
        res = await make_coro(check_func)(cog, obj, *args, **kwargs)
        if not res.status:
            if level is not None:
                log_func(cog.logger, level, f"{func.__name__}: failed check " 
                    f"'{check_func.__name__}'", *(obj, *args), **kwargs)
            if notify:
                raise CheckFailed(obj, res.msg)
        return res.status
    return action

def has_verified_role(cog, obj, *args, **kwargs):
    """Checks that user that invoked function has the verified role.

    Verified role defined in config.

    Associated cog must have bot as instance variable.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    member = get_member(cog.bot, obj.author)
    if member is None or VERIF_ROLE not in get_role_ids(member):
        return CheckResult(False, "You must be verified to do that.")
    return CheckResult(True, None)

def was_verified_user(cog, obj, *args, **kwargs):
    """Checks that user that invoked function was verified in past.
    
    Verified in past defined as either verified in the database or currently
    has verified rank (defined in config) in Discord.

    Associated cog must have bot and db as instance variables.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    if not (isinstance(obj, User) or isinstance(obj, Member)):
        obj = obj.author
    member = get_member(cog.bot, obj)
    if member is not None and VERIF_ROLE in get_role_ids(member):
        return CheckResult(True, None)
    try:
        member_data = cog.db.get_member_data(obj.id)
        if member_data[MemberKey.ID_VER]:
            return CheckResult(True, None)
    except MemberNotFound:
        pass
    return CheckResult(False, "You must be verified to do that.")

def is_unverified_user(cog, obj, *args, **kwargs):
    """Checks that user that invoked function is unverified.

    Verified role defined in config.

    Associated cog must have bot as instance variable.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    member = get_member(cog.bot, obj.author)
    if member is not None and VERIF_ROLE in get_role_ids(member):
        return CheckResult(False, "You are already verified.")
    return CheckResult(True, None)

def verified_in_db(cog, obj, *args, **kwargs):
    """Checks that user that invoked function is verified in database.

    Associated cog must have bot and db as instance variables.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    member = obj
    if not (isinstance(obj, User) or isinstance(obj, Member)):
        member = obj.author
    try:
        member_data = cog.db.get_member_data(member.id)
        if member_data[MemberKey.ID_VER]:
            return CheckResult(True, None)
    except MemberNotFound:
        pass
    return CheckResult(False, "Could not find your details in the database. "
        "Please contact an admin.")

def never_verified_user(cog, obj, *args, **kwargs):
    """Checks that user that invoked function was never verified in past.
    
    Verified in past defined as either verified in the database or currently
    has verified rank (defined in config) in Discord.

    Associated cog must have bot and db as instance variables.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    member = get_member(cog.bot, obj.author)
    if member is None or VERIF_ROLE not in get_role_ids(member):
        try:
            member_data = cog.db.get_member_data(obj.author.id)
        except MemberNotFound:
            return CheckResult(True, None)
        if not member_data[MemberKey.ID_VER]:
            return CheckResult(True, None)
    return CheckResult(False, "You are already verified.")

def is_admin_user(cog, obj, *args, **kwargs):
    """Checks that user that invoked function has at least one admin role.

    Admin roles defined in config.

    Associated cog must have bot as instance variable.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    member = get_member(cog.bot, obj.author)
    if set(ADMIN_ROLES).isdisjoint(get_role_ids(member)):
        return CheckResult(False, "You are not authorised to do that.")
    return CheckResult(True, None)

def is_guild_member(cog, obj, *args, **kwargs):
    """Checks that user that invoked function is member of guild.
    
    Guild defined in config.

    Associated cog must have bot as instance variable.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    if get_member(cog.bot, obj.author) is None:
        return CheckResult(False, "You must be a member of the server to do "
            "that.")
    return CheckResult(True, None)

def in_ver_channel(cog, obj, *args, **kwargs):
    """Checks that function was invoked in verification channel.
    
    Verification channel defined in config.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    ver_channel = cog.guild.get_channel(VER_CHANNEL)
    if obj.channel.id != ver_channel.id:
        return CheckResult(False, "That command can only be used in "
            f"{ver_channel.mention}.")
    return CheckResult(True, None)

def in_admin_channel(cog, obj, *args, **kwargs):
    """Checks that function was invoked in admin channel.
    
    Admin channel defined in config.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    if obj.channel.id != ADMIN_CHANNEL:
        return CheckResult(False, "You must be in the admin channel to do "
            "that.")
    return CheckResult(True, None)

def in_dm_channel(cog, obj, *args, **kwargs):
    """Checks that function was invoked in DM channel.
    
    Admin channel defined in config.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    if obj.guild is not None:
        return CheckResult(False, "You must be in a DM channel to do that.")
    return CheckResult(True, None)

def is_human(cog, obj, *args, **kwargs):
    """Checks that function was invoked by human user.
    
    Prevents bot from handling events triggered by bots, including itself.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    if not (isinstance(obj, User) or isinstance(obj, Member)):
        obj = obj.author
    if obj.bot:
        return CheckResult(False, "You are not human.")
    return CheckResult(True, None)

def is_not_command(cog, message, *args, **kwargs):
    """Checks that message that invoked function was not a command.

    Prevents bot from handling on_message events generated by commands.

    Args:
        cog: Cog associated with function invocation.
        obj: Object associated with function invocation.

    Returns:
        1. Boolean result of check.
        2. Error message to supply, if check failed.
    """
    if message.content.startswith(PREFIX) \
        and cog.bot.get_command(message.content.split(" ")[0][1:]):
        return CheckResult(False, "That is a command.")
    return CheckResult(True, None)

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
