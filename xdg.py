import os

_home = os.environ['HOME']
config_home = os.environ.get('XDG_CONFIG_HOME', _home + '/.config')
data_home = os.environ.get('XDG_DATA_HOME', _home + '/.local/share')
cache_home = os.environ.get('XDG_CACHE_HOME', _home + '/.cache')
