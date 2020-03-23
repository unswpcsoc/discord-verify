from discord import DMChannel
from discord.ext.commands import CheckFailure
from functools import wraps
from inspect import iscoroutinefunction

from botcore.config import config

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
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cog = args[0]
            ctx = args[1]
            if not predicate(cog, ctx):
                return
            return await func(*args, **kwargs)
        return wrapper

    if iscoroutinefunction(predicate):
        decorator.predicate = predicate
    else:
        @wraps(predicate)
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
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        member = cog.bot.get_guild(config["server-id"]).get_member(ctx.author.id)
        if member is None or config["verified-role"] not in map(lambda r: r.id, member.roles):
            if error:
                await ctx.send("You must be verified to do that.")
            return False
        return True
    return check(predicate)

def was_verified_user(error=False):
    """
    Decorator. Only allows method to execute if invoker is verified in the
    database.
    Cog must have bot and db as instance variables.

    Args:
        error: Whether to send error message if check fails.
    """

    def currently_verified(cog, ctx):
        member = cog.bot.get_guild(config["server-id"]).get_member(ctx.author.id)
        if member is None or config["verified-role"] not in map(lambda r: r.id, member.roles):
            return False
        return True

    def predicate(cog, ctx):
        if currently_verified(cog, ctx):
            return True
        member_info = cog.db.collection("members").document(str(ctx.author.id)).get().to_dict()
        if member_info == None or not member_info["verified"]:
            if error:
                await ctx.send("You must be verified to do that.")
            return False
        return True

    return check(predicate)

def is_unverified_user(error=False):
    """
    Decorator. Only allows method to execute if invoker does not have the
    verified role defined in the config.
    Cog must have bot as an instance variable.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        member = cog.bot.get_guild(config["server-id"]).get_member(ctx.author.id)
        if member is not None and config["verified-role"] in map(lambda r: r.id, member.roles):
            if error:
                await ctx.send("You are already verified.")
            return False
        return True
    return check(predicate)

def never_verified_user(error=False):
    """
    Decorator. Only allows method to execute if invoker was never verified in
    the database.
    Cog must have bot and db as instance variables.

    Args:
        error: Whether to send error message if check fails.
    """

    def currently_verified(cog, ctx):
        member = cog.bot.get_guild(config["server-id"]).get_member(ctx.author.id)
        if member is None or config["verified-role"] not in map(lambda r: r.id, member.roles):
            return False
        return True

    def predicate(cog, ctx):
        if not currently_verified(cog, ctx):
            member_info = cog.db.collection("members").document(str(ctx.author.id)).get().to_dict()
            if member_info == None or not member_info["verified"]:
                return True
        if error:
            await ctx.send("You are already verified.")
        return False

    return check(predicate)

def is_admin_user(error=False):
    """
    Decorator. Only allows method to execute if invoker has at least one admin
    role as defined in the config.
    Cog must have bot as an instance variable.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        member = cog.bot.get_guild(config["server-id"]).get_member(ctx.author.id)
        if set(config["admin-roles"]).isdisjoint(map(lambda r: r.id, member.roles)):
            if error:
                await ctx.send("You are not authorised to do that.")
            return False
        return True
    return check(predicate)

def is_guild_member(error=False):
    """
    Decorator. Only allows method to execute if invoked by a member of the guild
    defined in the config.
    Cog must have bot as an instance variable.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        if cog.bot.get_guild(config["server-id"]).get_member(ctx.author.id) is None:
            if error:
                await ctx.send("You must be a member of the server to do that.")
            return False
        return True
    return check(predicate)

def in_allowed_channel(error=False):
    """
    Decorator. Only allows method to execute if invoked in an allowed channel as
    defined in the config.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        if ctx.channel.id not in config["allowed-channels"]:
            if error:
                await ctx.send("You cannot do that in this channel.")
            return False
        return True
    return check(predicate)

def in_admin_channel(error=False):
    """
    Decorator. Only allows method to execute if invoked in the admin channel
    defined in the config.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        if ctx.channel.id != config["admin-channel"]:
            if error:
                await ctx.send("You must be in the admin channel to do that.")
            return False
        return True
    return check(predicate)

def in_dm_channel(error=False):
    """
    Decorator. Only allows method to execute if invoked in a DM channel.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        if ctx.guild is not None:
            if error:
                await ctx.send("You must be in a DM channel to do that.")
            return False
        return True
    return check(predicate)

def is_human():
    """
    Decorator. Prevents the bot from handling events triggered by bots,
    including itself.
    """
    
    def predicate(cog, ctx):
        if ctx.author.bot:
            return False
        return True
    return check(predicate)

def is_not_command():
    """
    Decorator. Prevents the bot from handling on_message events generated by
    commands.
    """

    def predicate(cog, ctx):
        if ctx.content.startswith(config["command-prefix"]):
            return False
        return True
    return check(predicate)
