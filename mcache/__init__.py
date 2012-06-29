import mailbox
import os.path
import logging

try:
    import cPickle as pickle
except ImportError:
    import pickle

logger = logging.getLogger(__name__)

class Cache(object):
    headers = (
        'Message-Id',
        'From',
        'Subject',
        'References',
        'In-Reply-To'
    )

    def __init__(self, cache):
        self._cache_path = os.path.abspath(cache)
        self._cache = {}
        self._resolve = {}

    def __getitem__(self, key):
        if isinstance(key, tuple):
            key = self._resolve[key]
        return self._cache[key]

    def __setitem__(self, key, value):
        messageId = value['Message-Id']
        if isinstance(key, tuple):
            self._resolve[key] = messageId
        elif messageId != key:
            raise Exception('message id mismatch')
        slim = [(k, value[k]) for k in self.headers if k in value]
        self._cache[messageId] = slim

    def load(self):
        logger.debug('loading header cache')
        with open(self._cache_path, 'rb') as f:
            data = pickle.load(f)
        self._cache.update(data['messages'])
        self._resolve.update(data['resolve'])
        logger.info('Cache contains (%d messages, %d mappings)' % (
            len(self._cache),
            len(self._resolve)
        ))

    def save(self):
        logger.debug('saving header cache')
        dir = os.path.dirname(self._cache_path)
        if not os.path.exists(dir):
            os.makedirs(dir, 0o700)
        mode = os.O_WRONLY | os.O_CREAT
        with os.fdopen(os.open(self._cache_path, mode, 0o600), 'wb') as f:
            pickle.dump({
                'messages': self._cache,
                'resolve': self._resolve
            }, f)


class HeaderCache(object):
    def __init__(self, mailbox, cache):
        self._mailbox = mailbox
        self._cache = cache

    def __getitem__(self, key):
        try:
            headers = self._cache[('maildir', key)]
        except KeyError:
            logger.debug('cache miss')
            return self._mailbox[key]
        msg = mailbox.Message()
        msg._headers = headers
        return msg

    def __setitem__(self, key, value):
        self._cache[('maildir', key)] = value

    def keys(self):
        return self._mailbox.keys()

    def __iter__(self):
        for key in self.keys():
            try:
                value = self[key]
            except KeyError:
                continue
            yield value

    def load(self):
        self._cache.load()

    def save(self):
        self._cache.save()


class HeaderCached(mailbox.Maildir):
    def _update_cache(self, key, message):
        self.header_cache[('maildir', key)] = message

    def __setitem__(self, key, message):
        super(HeaderCached, self).__getitem__(key, message)
        self._update_cache(key, message)

    def __getitem__(self, key):
        message = super(HeaderCached, self).__getitem__(key)
        self._update_cache(key, message)
        return message
