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

CONSOLE_LOG_LVL = logging.INFO
CONSOLE_LOG_FMT = "[%(asctime)s] [%(module)s/%(levelname)s]: %(message)s"
CONSOLE_TIME_FMT = "%H:%M:%S"

FILE_LOG_LVL = logging.DEBUG
FILE_LOG_FMT = "[%(asctime)s] [%(module)s/%(levelname)s]: %(message)s"
FILE_TIME_FMT = "%Y-%m-%d %H:%M:%S"

FILENAME_TIME_FMT = "%Y-%m-%d_%H-%M-%S"
FILENAME = f"{strftime(FILENAME_TIME_FMT, localtime(time()))}.log"

def new_logger():
    import logging

    logger = logging.getLogger(__name__)
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
