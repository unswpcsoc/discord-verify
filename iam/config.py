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

"""Handle loading config file."""

import yaml

class ConfigFileNotFound(FileNotFoundError):
    """Config file does not exist."""
    pass

CONFIG_DIR = "config"
CONFIG_FILE = f"{CONFIG_DIR}/config.yml"

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as fs:
        config = yaml.load(fs, Loader=yaml.SafeLoader)
    BOT_TOKEN = config["bot-token"]
    PREFIX = config["command-prefix"]
    SERVER_ID = config["server-id"]
    VER_ROLE = config["verified-role"]
    VER_CHANNEL = config["verification-channel"]
    MAX_VER_EMAILS = config["max-verification-emails"]
    ADMIN_CHANNEL = config["admin-channel"]
    ADMIN_ROLES = config["admin-roles"]
    EMAIL = config["email-address"]
    AWS_REGION = config["aws-region"]
    AWS_ACCESS_KEY_ID = config["aws-access-key-id"]
    AWS_SECRET_ACCESS_KEY = config["aws-secret-access-key"]
except IOError as err:
    raise ConfigFileNotFound("Can't find config file! Create a config.yml "
        "file in the config directory with similar structure to default.yml.")
