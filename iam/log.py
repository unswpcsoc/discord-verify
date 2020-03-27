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

"""Handle creation of loggers."""

import logging
from time import time, localtime, strftime
from discord import Message, Member
from discord.ext.commands import Context

CONSOLE_LOG_LVL = logging.INFO
"""Console logging level."""
CONSOLE_LOG_FMT = "[%(asctime)s] [%(module)s/%(levelname)s]: %(message)s"
"""Console logging format."""
CONSOLE_TIME_FMT = "%H:%M:%S"
"""Console log timestamp format."""

FILE_LOG_LVL = logging.DEBUG
"""File logging level."""
FILE_LOG_FMT = ("[%(asctime)s] [%(module)s/%(funcName)s/%(levelname)s]: "
                "%(message)s")
"""File logging format."""
FILE_TIME_FMT = "%Y-%m-%d %H:%M:%S"
"""File log timestamp format."""

FILENAME_TIME_FMT = "%Y-%m-%d_%H-%M-%S"
"""Log filename timestamp format."""
FILENAME = f"logs/{strftime(FILENAME_TIME_FMT, localtime(time()))}.log"
"""Log filename format."""

def new_logger(name):
    """Create a new logger with the given name.

    Initialise it with constants set at the top of log.py.

    Args:
        name: String representing name of the logger to be created.

    Returns:
        The new logger.
    """
    import logging

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    c_handler = logging.StreamHandler()
    c_handler.setLevel(CONSOLE_LOG_LVL)
    c_formatter = logging.Formatter(CONSOLE_LOG_FMT, CONSOLE_TIME_FMT)
    c_handler.setFormatter(c_formatter)
    logger.addHandler(c_handler)

    f_handler = logging.FileHandler(FILENAME)
    f_handler.setLevel(FILE_LOG_LVL)
    f_formatter = logging.Formatter(FILE_LOG_FMT, FILE_TIME_FMT)
    f_handler.setFormatter(f_formatter)
    logger.addHandler(f_handler)

    return logger

def log_event(cog, object, level, meta):
    """Logs an event and information about its invocation.

    Cog must have log as an instance variable.

    Args:
        cog: Cog attached to event invocation.
        object: Object attached to event invocation.
        level: Logging level to log at.
        meta: String representing info about event.
    """
    object_dict = OBJECT_TO_DICT[type(object)](object)
    cog.log.log(level, f"{meta} - {type(object).__name__}: {str(object_dict)}")

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
        "message_id": ctx.message.id
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
        "guild": guild.id if guild is not None else None
    }

def member_to_dict(member):
    """Convert Member object into dict containing their info.

    Args:
        member: Member object to be converted.

    Returns:
        Dict containing information about member.
    """
    return {
        "handle": f"{member.name}#{member.discriminator}",
        "id": member.id,
        "guild": member.guild.id
    }

OBJECT_TO_DICT = {
    Context: context_to_dict,
    Message: message_to_dict,
    Member: message_to_dict,
}
"""Maps types to dict converter functions."""
