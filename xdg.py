import os.path

class Context(object):
    def __init__(self, app):
        self._app = app
        self.home = os.environ['HOME']
        self.config_home = os.environ.get(
            'XDG_CONFIG_HOME',
            os.path.join(self.home, '.config')
        )
        self.data_home = os.environ.get(
            'XDG_DATA_HOME',
            os.path.join(self.home, 'local', 'share')
        )
        self.cache_home = os.environ.get(
            'XDG_CACHE_HOME',
            os.path.join(self.home, '.cache')
        )

    def config(self, *path):
        return os.path.join(self.config_home, self._app, *path)

    def data(self, *path):
        return os.path.join(self.data_home, self._app, *path)

    def cache(self, *path):
        return os.path.join(self.cache_home, self._app, *path)
