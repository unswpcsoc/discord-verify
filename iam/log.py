"""Handle creation of loggers."""

import logging
from time import time, localtime, strftime
from collections import defaultdict
# from discord import Message, Member, User
# from discord.ext.commands import Context
from nextcord import Message, Member, User
from nextcord.ext.commands import Context

CONSOLE_LOG_FMT = "[%(asctime)s] [%(module)s/%(levelname)s]: %(message)s"
"""Console logging format."""
CONSOLE_TIME_FMT = "%H:%M:%S"
"""Console log timestamp format."""

FILE_LOG_FMT = "[%(asctime)s] [%(module)s/%(funcName)s/%(levelname)s]: " "%(message)s"
"""File logging format."""
FILE_TIME_FMT = "%Y-%m-%d %H:%M:%S"
"""File log timestamp format."""

FILENAME_TIME_FMT = "%Y-%m-%d_%H-%M-%S"
"""Log filename timestamp format."""
FILENAME = f"logs/{strftime(FILENAME_TIME_FMT, localtime(time()))}.log"
"""Log filename format."""


def new_logger(name, c_level=logging.INFO, f_level=logging.DEBUG):
    """Create a new logger with the given name.

    Initialise it with constants set at the top of log.py.

    Args:
        name: String representing name of the logger to be created.
        c_level: Logging level for console.
        f_level: Logging level for file.

    Returns:
        The new logger.
    """
    import logging

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    c_handler = logging.StreamHandler()
    c_handler.setLevel(c_level)
    c_formatter = logging.Formatter(CONSOLE_LOG_FMT, CONSOLE_TIME_FMT)
    c_handler.setFormatter(c_formatter)
    logger.addHandler(c_handler)

    f_handler = logging.FileHandler(FILENAME)
    f_handler.setLevel(f_level)
    f_formatter = logging.Formatter(FILE_LOG_FMT, FILE_TIME_FMT)
    f_handler.setFormatter(f_formatter)
    logger.addHandler(f_handler)

    return logger


def log_func(logger, level, meta, *args, **kwargs):
    """Logs a function call and its args/kwargs.

    Args:
        logger: Logger to write log to.
        level: Logging level to log at.
        meta: String representing info about function, including name.
        *args: Args supplied to function call.
        **kwargs: Keyword args supplied to function call.
    """
    arg_reps = []
    for arg in args:
        arg_dict = OBJECT_TO_REP[type(arg)](arg)
        arg_reps.append(f"{type(arg).__name__}: {str(arg_dict)}")
    logger.log(level, " - ".join([meta, ", ".join(arg_reps)]))


def context_to_dict(ctx):
    """Convert Context object into dict containing their info.

    Args:
        ctx: Context object to be converted.

    Returns:
        Dict containing information about ctx.
    """
    return {
        "content": ctx.message.content,
        "user": ctx.author.id,
        "channel": ctx.channel.id,
        "guild": ctx.guild.id if ctx.guild is not None else None,
        "message_id": ctx.message.id,
    }


def message_to_dict(message):
    """Convert Message object into dict containing their info.

    Args:
        message: Message object to be converted.

    Returns:
        Dict containing information about message.
    """
    guild = message.guild
    return {
        "content": message.content,
        "id": message.id,
        "user": message.author.id,
        "channel": message.channel.id,
        "guild": guild.id if guild is not None else None,
    }


def user_to_dict(user):
    """Convert user object into dict containing their info.

    Args:
        user: user object to be converted.

    Returns:
        Dict containing information about user.
    """
    return {"handle": f"{user.name}#{user.discriminator}", "id": user.id}


OBJECT_TO_REP = defaultdict(lambda: str)
OBJECT_TO_REP[Context] = context_to_dict
OBJECT_TO_REP[Message] = message_to_dict
OBJECT_TO_REP[Member] = user_to_dict
OBJECT_TO_REP[User] = user_to_dict
"""Maps types to functions to convert param to type representable as string."""
