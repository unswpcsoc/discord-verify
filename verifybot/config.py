import yaml

class ConfigFileNotFound(FileNotFoundError):
    pass

config_dir = "../config"
config_file = f"{config_dir}/config.yml"

try:
    with open(config_file, "r", encoding="utf-8") as fs:
        config = yaml.load(fs)
except IOError as err:
    raise ConfigFileNotFound("Can't find config file! Create a config.yml file \
        in the config directory with similar structure to default.yml.")

BOT_TOKEN = config["bot-token"]
COMMAND_PREFIX = config["command-prefix"]
ALLOWED_CHANNELS = config["allowed-channels"]
ADMIN_CHANNELS = config["admin-channels"]
ADMIN_ROLES = config["admin-roles"]
