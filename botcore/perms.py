from discord import DMChannel
from discord.ext import commands

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
# defined in the config.
def is_verified_user():
    def predicate(ctx):
        if config["verified-role"] not in map(lambda r: r.id, ctx.author.roles):
            raise NotVerified("You must be verified to do that.")
        return True
    return commands.check(predicate)

# Decorator. Only allows command to execute if invoker does not have the
# verified role as defined in the config.
def is_unverified_user():
    def predicate(ctx):
        if config["verified-role"] in map(lambda r: r.id, ctx.author.roles):
            raise AlreadyVerified("You are already verified.")
        return True
    return commands.check(predicate)

# Decorator. Only allows command to execute if invoker has at least one admin
# role as defined in the config.
def is_admin_user():
    def predicate(ctx):
        if set(config["admin-roles"]).isdisjoint(map(lambda r: r.id, ctx.author.roles)):
            raise NotAdminUser("You are not authorised to do that.")
        return True
    return commands.check(predicate)

# Decorator. Only allows command to execute if invoked in an allowed channel as
# defined in the config.
def in_allowed_channel():
    def predicate(ctx):
        if ctx.channel.id not in config["allowed-channels"]:
            raise NotAllowedChannel("You cannot do that in this channel.")
        return True
    return commands.check(predicate)

# Decorator. Only allows command to execute if invoked in the admin channel
# defined in the config.
def in_admin_channel():
    def predicate(ctx):
        if ctx.channel.id != config["admin-channel"]:
            raise NotAdminChannel("You must be in the admin channel to do that.")
        return True
    return commands.check(predicate)
