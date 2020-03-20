import yaml

config_file = "../config.yml"
with open(config_file, "r", encoding="utf-8") as fs:
    config = yaml.load(fs)

BOT_TOKEN = config["bot-token"]
COMMAND_PREFIX = config["command-prefix"]
ALLOWED_CHANNELS = config["allowed-channels"]
ADMIN_ROLES = config["admin-roles"]
