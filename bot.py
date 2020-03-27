#!/usr/bin/env python3

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

"""Launches the Discord bot."""

import sys
from discord.ext import commands

from iam.log import new_logger
from iam.config import BOT_TOKEN, PREFIX

LOG = None

def main():
    global LOG
    new_logger("discord")
    LOG = new_logger(__name__)
    sys.excepthook = exception_handler

    BOT = commands.Bot(command_prefix=PREFIX)

    BOT.load_extension("iam.core")
    BOT.load_extension("iam.db")
    BOT.load_extension("iam.mail")
    BOT.load_extension("iam.verify")
    BOT.load_extension("iam.sign")

    BOT.run(BOT_TOKEN)

def exception_handler(type, value, traceback):
    LOG.exception(f"Uncaught exception: {value}")

if __name__ == "__main__":
    main()
