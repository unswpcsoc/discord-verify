from discord import DMChannel
from discord.ext import commands
import inspect
import functools

from botcore.config import config

class NotVerified(commands.CheckFailure):
    pass

class AlreadyVerified(commands.CheckFailure):
    pass

class NotAdminUser(commands.CheckFailure):
    pass

class NotAllowedChannel(commands.CheckFailure):
    pass

class NotAdminChannel(commands.CheckFailure):
    pass

# Decorator. Only allows command to execute if invoker has the verified role as
# defined in the config. Raises NotVerified otherwise.
def is_verified_user():
    def predicate(ctx):
        if config["verified-role"] not in map(lambda r: r.id, ctx.author.roles):
            raise NotVerified("You must be verified to do that.")
        return True
    return commands.check(predicate)

# Decorator. Only allows command to execute if invoker does not have the
# verified role as defined in the config. Raises AlreadyVerified otherwise.
def is_unverified_user():
    def predicate(ctx):
        if config["verified-role"] in map(lambda r: r.id, ctx.author.roles):
            raise AlreadyVerified("You are already verified.")
        return True
    return commands.check(predicate)

# Decorator. Only allows command to execute if invoker has at least one admin
# role as defined in the config. Raises NotAdminUser otherwise.
def is_admin_user():
    def predicate(ctx):
        if set(config["admin-roles"]).isdisjoint(map(lambda r: r.id, ctx.author.roles)):
            raise NotAdminUser("You are not authorised to do that.")
        return True
    return commands.check(predicate)

# Decorator. Only allows command to execute if invoked in an allowed channel as
# defined in the config. Raises NotAllowedChannel otherwise.
def in_allowed_channel():
    def predicate(ctx):
        if ctx.channel.id not in config["allowed-channels"]:
            raise NotAllowedChannel("You cannot do that in this channel.")
        return True
    return commands.check(predicate)

# Decorator. Only allows command to execute if invoked in the admin channel
# defined in the config. Raises NotAdminChannel otherwise.
def in_admin_channel():
    def predicate(ctx):
        if ctx.channel.id != config["admin-channel"]:
            raise NotAdminChannel("You must be in the admin channel to do that.")
        return True
    return commands.check(predicate)

# Decorator. Event is only handled if user in context has the verified role as
# defined in the config.
# Can only be used with cogs.
def listen_verified():
    def predicate(bot, ctx):
        member = bot.get_guild(config["server-id"]).get_member(ctx.author.id)
        if config["verified-role"] in map(lambda r: r.id, member.roles):
            return True
        return False
    return event_check(predicate)

# Decorator. Event is only handled if user in context does not have the verified
# role as defined in the config.
# Can only be used with cogs.
def listen_unverified():
    def predicate(bot, ctx):
        member = bot.get_guild(config["server-id"]).get_member(ctx.author.id)
        if config["verified-role"] in map(lambda r: r.id, member.roles):
            return False
        return True
    return event_check(predicate)

# Decorator. Event is only handled if context is a DM channel.
# Can only be used with cogs.
def listen_dm():
    def predicate(bot, ctx):
        if ctx.guild is None:
            return True
        return False
    return event_check(predicate)

# Decorator. Event is only handled if it passes a check in the form of the
# function predicate.
# Can only be used with cogs.
def event_check(predicate):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            bot = args[0].bot
            ctx = args[1]
            if not predicate(bot, ctx):
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
