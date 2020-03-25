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

from botcore.config import config

def check(predicate, error):
    """ Decorate method to only execute if it passes a check.
    
    Check is the function 'predicate'.

    Can only be used with cogs.

    Args:
        predicate: Function that takes in cog and context as args and returns
        boolean value representing result of a check. Need not be async, but
        can be.
        error: Boolean for whether to send error message if check fails.
    """
    async_predicate = predicate
    if not iscoroutinefunction(predicate):
        @wraps(predicate)
        async def wrapper(cog, ctx):
            return predicate(cog, ctx)
        async_predicate = wrapper

    def decorator(func):
        @wraps(func)
        async def wrapper(cog, ctx, *args, **kwargs):
            res, err_msg = await async_predicate(cog, ctx)
            if not res:
                if error:
                    await ctx.send(err_msg)
                return
            return await func(cog, ctx, *args, **kwargs)
        return wrapper

    return decorator

def is_verified_user(error=False):
    """Decorate method to only execute if invoker has verified role.
    
    Verified role defined in config.
    
    Cog must have bot as instance variable.

    Args:
        error: Boolean for whether to send error message if check fails.
    """
    def predicate(cog, ctx):
        member = _get_member(cog, ctx.author.id)
        if member is None or config["verified-role"] \
            not in _get_role_ids(member):
            return False, "You must be verified to do that."
        return True, None
    
    return check(predicate, error)

def was_verified_user(error=False):
    """Decorate method to only execute if invoker was verified in past.
    
    Verified in past defined as either verified in the database or currently
    has verified rank in Discord.

    Cog must have bot and db as instance variables.

    Args:
        error: Boolean for whether to send error message if check fails.
    """
    def currently_verified(cog, ctx):
        member = _get_member(cog, ctx.author.id)
        if member is None or config["verified-role"] \
            not in _get_role_ids(member):
            return False
        return True

    def predicate(cog, ctx):
        if currently_verified(cog, ctx):
            return True
        member_info = cog.db.get_member_data(ctx.author.id)
        if member_info == None or not member_info["verified"]:
            return False, "You must be verified to do that."
        return True, None

    return check(predicate, error)

def is_unverified_user(error=False):
    """Decorate method to only execute if invoker does not have verified role.

    Verified role defined in config.

    Cog must have bot as instance variable.

    Args:
        error: Boolean for whether to send error message if check fails.
    """
    def predicate(cog, ctx):
        member = _get_member(cog, ctx.author.id)
        if member is not None and config["verified-role"] \
            in _get_role_ids(member):
            return False, "You are already verified."
        return True, None
    
    return check(predicate, error)

def never_verified_user(error=False):
    """Decorate method to only execute if invoker was never verified.
    
    Verified defined as being verified in database.

    Cog must have bot and db as instance variables.

    Args:
        error: Boolean for whether to send error message if check fails.
    """
    def currently_verified(cog, ctx):
        member = _get_member(cog, ctx.author.id)
        if member is None or config["verified-role"] \
            not in _get_role_ids(member):
            return False
        return True

    def predicate(cog, ctx):
        if not currently_verified(cog, ctx):
            member_info = cog.db.get_member_data(ctx.author.id)
            if member_info == None or not member_info["verified"]:
                return True, None
        return False, "You are already verified."

    return check(predicate, error)

def is_admin_user(error=False):
    """Decorate method to only execute if invoker has at least one admin role.

    Admin roles defined in config
    
    Cog must have bot as instance variable.

    Args:
        error: Boolean for whether to send error message if check fails.
    """
    def predicate(cog, ctx):
        member = _get_member(cog, ctx.author.id)
        if set(config["admin-roles"]).isdisjoint(_get_role_ids(member)):
            return False, "You are not authorised to do that."
        return True, None
    return check(predicate, error)

def is_guild_member(error=False):
    """Decorate method to only execute if invoked by member of guild.
    
    Guild defined in config.

    Cog must have bot as instance variable.

    Args:
        error: Boolean for whether to send error message if check fails.
    """
    def predicate(cog, ctx):
        if _get_member(cog, ctx.author.id) is None:
            return False, "You must be a member of the server to do that."
        return True, None
    return check(predicate, error)

def in_allowed_channel(error=False):
    """Decorate method to only execute if invoked in an allowed channel.
    
    Allowed channels defined in config.

    Args:
        error: Boolean for whether to send error message if check fails.
    """
    def predicate(cog, ctx):
        if ctx.channel.id not in config["allowed-channels"]:
            return False, "You cannot do that in this channel."
        return True, None
    return check(predicate, error)

def in_admin_channel(error=False):
    """Decorate method to only execute if invoked in admin channel.
    
    Admin channel defined in config.

    Args:
        error: Boolean for whether to send error message if check fails.
    """
    def predicate(cog, ctx):
        if ctx.channel.id != config["admin-channel"]:
            return False, "You must be in the admin channel to do that."
        return True, None
    return check(predicate, error)

def in_dm_channel(error=False):
    """Decorate method to only execute if invoked in DM channel.

    Args:
        error: Boolean for whether to send error message if check fails.
    """
    def predicate(cog, ctx):
        if ctx.guild is not None:
            return False, "You must be in a DM channel to do that."
        return True, None
    return check(predicate, error)

def is_human():
    """Decorate method to only execute if invoked by human.
    
    Prevents bot from handling events triggered by bots, including itself.
    """
    def predicate(cog, ctx):
        if ctx.author.bot:
            return False, None
        return True, None
    return check(predicate, False)

def is_not_command():
    """Decorate method to only execute if not command.

    Prevents bot from handling on_message events generated by commands.

    Commands defined as starting with command prefix defined in config.
    """
    def predicate(cog, ctx):
        if ctx.content.startswith(config["command-prefix"]):
            return False, None
        return True, None
    return check(predicate, False)

def _get_member(cog, id):
    """Get member with given Discord ID.
    
    Args:
        cog: Cog that invoked this function. Must have bot as instance
             variable.
        id: Discord ID of member.

    Returns:
        The Member object associated with id and the guild defined in the
        config.
    """
    return cog.bot.get_guild(config["server-id"]).get_member(id)

def _get_role_ids(member):
    """Get list of IDs of all roles member has.

    Args:
        member: Member object.

    Returns:
        List of IDs of all roles member has.
    """
    return list(map(lambda r: r.id, member.roles))
