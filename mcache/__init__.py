import mailbox
import os.path
import logging

try:
    import cPickle as pickle
except ImportError:
    import pickle

logger = logging.getLogger(__name__)


class HeaderCache(dict):
    headers = (
        'Message-Id',
        'From',
        'Subject',
        'References',
        'In-Reply-To'
    )

    def __init__(self, mailbox, cache):
        self._mailbox = mailbox
        self._cache = os.path.abspath(cache)

    def __missing__(self, key):
        return self._mailbox[key]

    def keys(self):
        return self._mailbox.keys()

    def __iter__(self):
        for key in self.keys():
            try:
                value = self[key]
            except KeyError:
                continue
            yield value

    def thinmsg(self, src):
        msg = mailbox.Message()
        msg._headers = [(k, src[k]) for k in self.headers if k in src]
        return msg
    
    def load(self):
        logger.debug('loading header cache')
        with open(self._cache, 'rb') as f:
            self.update(pickle.load(f))

    def save(self):
        logger.debug('saving header cache')
        dir = os.path.dirname(self._cache)
        if not os.path.exists(dir):
            os.makedirs(dir, 0o700)
        mode = os.O_WRONLY | os.O_CREAT
        with os.fdopen(os.open(self._cache, mode, 0o600), 'wb') as f:
            pickle.dump([(key, self[key]) for key in dict.keys(self)], f)
        

class HeaderCached(mailbox.Maildir):

    def __init__(self, dirname, factory=None, create=None, cache=None):
        mailbox.Maildir.__init__(self, dirname, factory, create)
        self.header_cache = HeaderCache(self, cache)

    def _update_cache(self, key, message):
        self.header_cache[key] = self.header_cache.thinmsg(message)

    def __setitem__(self, key, message):
        super(HeaderCached, self).__getitem__(key, message)
        self._update_cache(key, message)

    def __getitem__(self, key):
        message = super(HeaderCached, self).__getitem__(key)
        self._update_cache(key, message)
        return message
