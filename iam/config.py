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
    VERIF_ROLE = config["verified-role"]
    VER_CHANNEL = config["verification-channel"]
    MAX_VER_EMAILS = config["max-verification-emails"]
    ADMIN_CHANNEL = config["admin-channel"]
    ADMIN_ROLES = config["admin-roles"]
    JOIN_ANNOUNCE_CHANNEL = config["join-announce-channel"]
    EMAIL = config["email-address"]
    AWS_REGION = config["aws-region"]
    AWS_ACCESS_KEY_ID = config["aws-access-key-id"]
    AWS_SECRET_ACCESS_KEY = config["aws-secret-access-key"]
    MAILCHIMP_API_KEY = config["mailchimp-api-key"]
    MAILCHIMP_LIST_ID = config["mailchimp-list-id"]
except IOError as err:
    raise ConfigFileNotFound(
        "Can't find config file! Create a config.yml "
        "file in the config directory with similar structure to default.yml."
    )
