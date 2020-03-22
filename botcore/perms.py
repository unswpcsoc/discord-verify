from discord import DMChannel
from discord.ext.commands import CheckFailure
import inspect
import functools

from botcore.config import config

class NotVerified(CheckFailure):
    pass

class AlreadyVerified(CheckFailure):
    pass

class NotAdminUser(CheckFailure):
    pass

class NotGuildMember(CheckFailure):
    pass

class NotAllowedChannel(CheckFailure):
    pass

class NotAdminChannel(CheckFailure):
    pass

class NotDMChannel(CheckFailure):
    pass

def check(predicate):
    """
    Decorator. Method is only handled if it passes a check in the form of the
    function predicate.
    Can only be used with cogs.

    Args:
        predicate: A function that takes in the cog and the context as arguments
            and returns a boolean value representing the result of a check.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cog = args[0]
            ctx = args[1]
            if not predicate(cog, ctx):
                return
            return await func(*args, **kwargs)
        return wrapper

    if inspect.iscoroutinefunction(predicate):
        decorator.predicate = predicate
    else:
        @functools.wraps(predicate)
        async def wrapper(ctx):
            return predicate(ctx)
        decorator.predicate = wrapper

    return decorator

def is_verified_user(error=False):
    """
    Decorator. Only allows method to execute if invoker has the verified role as
    defined in the config.
    Cog must have bot as an instance variable.

    Args:
        error: Whether to raise error if check fails.

    Raises:
        NotVerified: Check failed and error == True.
    """
    def predicate(cog, ctx):
        member = cog.bot.get_guild(config["server-id"]).get_member(ctx.author.id)
        if member is None or config["verified-role"] not in map(lambda r: r.id, member.roles):
            if error:
                raise NotVerified("You must be verified to do that.")
            return False
        return True
    return check(predicate)

def is_unverified_user(error=False):
    """
    Decorator. Only allows method to execute if invoker does not have the
    verified role defined in the config.
    Cog must have bot as an instance variable.

    Args:
        error: Whether to raise error if check fails.

    Raises:
        AlreadyVerified: Check failed and error == True.
    """
    def predicate(cog, ctx):
        member = cog.bot.get_guild(config["server-id"]).get_member(ctx.author.id)
        if member is not None and config["verified-role"] in map(lambda r: r.id, member.roles):
            if error:
                raise AlreadyVerified("You are already verified.")
            return False
        return True
    return check(predicate)

def is_admin_user(error=False):
    """
    Decorator. Only allows method to execute if invoker has at least one admin
    role as defined in the config.
    Cog must have bot as an instance variable.

    Args:
        error: Whether to raise error if check fails.

    Raises:
        NotAdminUser: Check failed and error == True.
    """
    def predicate(cog, ctx):
        if cog.bot.guild:
            if error:
                raise NotAdminUser("You are not authorised to do that.")
            return False
        return True
    return check(predicate)

def is_guild_member(error=False):
    """
    Decorator. Only allows method to execute if invoked by a member of the guild
    defined in the config.
    Cog must have bot as an instance variable.

    Args:
        error: Whether to raise error if check fails.

    Raises:
        NotGuildMember: Check failed and error == True.
    """
    def predicate(cog, ctx):
        if cog.bot.get_guild(config["server-id"]).get_member(ctx.author.id) is None:
            if error:
                raise NotGuildMember("You must be a member of the server to do that.")
            return False
        return True
    return check(predicate)

def in_allowed_channel(error=False):
    """
    Decorator. Only allows method to execute if invoked in an allowed channel as
    defined in the config.

    Args:
        error: Whether to raise error if check fails.

    Raises:
        NotAllowedChannel: Check failed and error == True.
    """
    def predicate(cog, ctx):
        if ctx.channel.id not in config["allowed-channels"]:
            if error:
                raise NotAllowedChannel("You cannot do that in this channel.")
            return False
        return True
    return check(predicate)

def in_admin_channel(error=False):
    """
    Decorator. Only allows method to execute if invoked in the admin channel
    defined in the config.

    Args:
        error: Whether to raise error if check fails.

    Raises:
        NotAdminChannel: Check failed and error == True.
    """
    def predicate(cog, ctx):
        if ctx.channel.id != config["admin-channel"]:
            if error:
                raise NotAdminChannel("You must be in the admin channel to do that.")
            return False
        return True
    return check(predicate)

def in_dm_channel(error=False):
    """
    Decorator. Only allows method to execute if invoked in a DM channel.

    Args:
        error: Whether to raise error if check fails.

    Raises:
        NotDMChannel: Check failed and error == True.
    """
    def predicate(cog, ctx):
        if ctx.guild is not None:
            if error:
                raise NotDMChannel("You must be in a DM channel to do that.")
            return False
        return True
    return check(predicate)
