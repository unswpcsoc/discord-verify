from functools import wraps
from inspect import iscoroutinefunction

from botcore.config import config

def check(predicate, error):
    """
    Decorator. Method is only handled if it passes a check in the form of the
    function predicate.
    Can only be used with cogs.

    Args:
        predicate: A function that takes in the cog and the context as 
            arguments and returns a boolean value representing the result of a
            check. Does not need to be async, but can be.
        error: Whether to send error message if check fails.
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
    """
    Decorator. Only allows method to execute if invoker has the verified role 
    as defined in the config.
    Cog must have bot as an instance variable.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        member = _get_member(cog, ctx.author.id)
        if member is None or config["verified-role"] \
            not in _get_role_ids(member):
            return False, "You must be verified to do that."
        return True, None
    
    return check(predicate, error)

def was_verified_user(error=False):
    """
    Decorator. Only allows method to execute if invoker is verified in the
    database.
    Cog must have bot and db as instance variables.

    Args:
        error: Whether to send error message if check fails.
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
    """
    Decorator. Only allows method to execute if invoker does not have the
    verified role defined in the config.
    Cog must have bot as an instance variable.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        member = _get_member(cog, ctx.author.id)
        if member is not None and config["verified-role"] \
            in _get_role_ids(member):
            return False, "You are already verified."
        return True, None
    
    return check(predicate, error)

def never_verified_user(error=False):
    """
    Decorator. Only allows method to execute if invoker was never verified in
    the database.
    Cog must have bot and db as instance variables.

    Args:
        error: Whether to send error message if check fails.
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
    """
    Decorator. Only allows method to execute if invoker has at least one admin
    role as defined in the config.
    Cog must have bot as an instance variable.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        member = _get_member(cog, ctx.author.id)
        if set(config["admin-roles"]).isdisjoint(_get_role_ids(member)):
            return False, "You are not authorised to do that."
        return True, None
    return check(predicate, error)

def is_guild_member(error=False):
    """
    Decorator. Only allows method to execute if invoked by a member of the
    guild defined in the config.
    Cog must have bot as an instance variable.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        if _get_member(cog, ctx.author.id) is None:
            return False, "You must be a member of the server to do that."
        return True, None
    return check(predicate, error)

def in_allowed_channel(error=False):
    """
    Decorator. Only allows method to execute if invoked in an allowed channel
    as defined in the config.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        if ctx.channel.id not in config["allowed-channels"]:
            return False, "You cannot do that in this channel."
        return True, None
    return check(predicate, error)

def in_admin_channel(error=False):
    """
    Decorator. Only allows method to execute if invoked in the admin channel
    defined in the config.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        if ctx.channel.id != config["admin-channel"]:
            return False, "You must be in the admin channel to do that."
        return True, None
    return check(predicate, error)

def in_dm_channel(error=False):
    """
    Decorator. Only allows method to execute if invoked in a DM channel.

    Args:
        error: Whether to send error message if check fails.
    """

    def predicate(cog, ctx):
        if ctx.guild is not None:
            return False, "You must be in a DM channel to do that."
        return True, None
    return check(predicate, error)

def is_human():
    """
    Decorator. Prevents the bot from handling events triggered by bots,
    including itself.
    """
    
    def predicate(cog, ctx):
        if ctx.author.bot:
            return False, None
        return True, None
    return check(predicate, False)

def is_not_command():
    """
    Decorator. Prevents the bot from handling on_message events generated by
    commands.
    """

    def predicate(cog, ctx):
        if ctx.content.startswith(config["command-prefix"]):
            return False, None
        return True, None
    return check(predicate, False)

def _get_member(cog, id):
    """
    Args:
        cog: The cog that invoked this function. cog must have bot as an 
        instance variable.
        id: Discord ID of a member.

    Returns:
        The Member object associated with id and the guild defined in the
        config.
    """

    return cog.bot.get_guild(config["server-id"]).get_member(id)

def _get_role_ids(member):
    """
    Args:
        member: A Member object.

    Returns:
        A list of IDs of all roles the member has.
    """

    return list(map(lambda r: r.id, member.roles))
