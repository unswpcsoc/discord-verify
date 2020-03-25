import yaml

class ConfigFileNotFound(FileNotFoundError):
    pass

CONFIG_DIR = "config"
CONFIG_FILE = f"{CONFIG_DIR}/config.yml"

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as fs:
        config = yaml.load(fs)
except IOError as err:
    raise ConfigFileNotFound("Can't find config file! Create a config.yml file \
        in the config directory with similar structure to default.yml.")
