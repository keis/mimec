import logging
import xdg
import json
import os

logger = logging.getLogger(__name__)


class App:
    def __init__(self, name, config=None):
        self.xdg = xdg.Context(name)
        self.config = config or {}
        self.state = {}
        self.load_config()
        self.load_state()

    def load_config(self):
        try:
            with open(self.xdg.config('config')) as f:
                self.config.update(json.loads(f.read()))
        except IOError:
            logger.info('could not read config file', exc_info=True)

    def load_state(self):
        state_file = self.xdg.config('state')
        try:
            with open(state_file, 'r') as cfg:
                self.state = json.loads(cfg.read())
        except IOError:
            self.state = {}
            logger.info('could not open state file', exc_info=True)

    def save_state(self):
        state_file = self.xdg.config('state')
        state_dir = os.path.dirname(state_file)
        try:
            if not os.path.exists(state_dir):
                os.makedirs(state_dir)
            with open(self.xdg.config('state'), 'w') as cfg:
                cfg.write(json.dumps(self.state))
        except IOError:
            logger.info('could not open state file', exc_info=True)
