import os.path
import logging
import mailbox
from collections import defaultdict, namedtuple

try:
    import cPickle as pickle
except ImportError:
    import pickle

logger = logging.getLogger(__name__)


class Cache(object):
    '''A Cache of message meta data

    The cache is queried using a Message-Id or a `pathspec`, a 2-tuple with
    (provider, uniqueid). The id of the pathspec should be enough for a loader
    to load the same message so e.g a uniqueid could be a path to a message on
    disk.

    The cache also maintains a index from Message-Id to possible `pathspec`s
    and from `pathspec` to it's Message-Id
    '''

    # pathspec constructor
    pathspec = namedtuple('pathspec', ('provider', 'spec'))

    # headers to cache
    headers = (
        'Message-Id',
        'From',
        'Subject',
        'References',
        'In-Reply-To'
    )

    def __init__(self, cache):
        self._cache_path = os.path.abspath(cache)
        # Mapping Message-Id -> list of tuple with (Header, Value)
        self._cache = {}
        # Mapping pathspec -> Message-Id
        self._resolve = {}
        # Mapping Message-Id -> list of pathspec
        self._index = defaultdict(set)

    def __getitem__(self, key):
        '''Get cached headers by Message-Id or pathspec'''
        if isinstance(key, tuple):
            key = self._resolve[key]
        return self._cache[key]

    # Should this perhaps be renamed to .cache()
    # cache[key] = x; x' = cache[key]; x == x' does not hold
    def __setitem__(self, key, value):
        '''Set cached headers by Message-Id or pathspec

        `value` can be either a `email.message.Message` or anything implementing
        the mapping protocol and will be used to fetch the headers that will be
        cached.

        if `key` is a pathspec a entry in the index will be made as well
        '''
        message_id = value['Message-Id']
        if isinstance(key, tuple):
            if len(key) != 2:
                raise TypeError('Tuple of size 2 expected got %s %r' % (len(key), key))
            self._resolve[key] = message_id
            self._index[message_id].add(key)
        elif messageId != key:
            raise Exception('message id mismatch')
        slim = [(k, value[k]) for k in self.headers if k in value]
        self._cache[message_id] = slim

    def lookup(self, message_id):
        '''Get a list of `pathspec`s providing the message with the given id'''
        return self._index[message_id]

    def load(self):
        '''Unserialise cache'''
        logger.debug('loading header cache')
        with open(self._cache_path, 'rb') as f:
            data = pickle.load(f)
        self._cache.update(data['messages'])
        self._resolve.update(data['resolve'])
        self._index.update(data['index'])
        logger.info('Cache contains (%d messages, %d mappings, %d path index entries)' % (
            len(self._cache),
            len(self._resolve),
            len(self._index)
        ))

    def save(self):
        '''Serialise cache'''
        logger.debug('saving header cache')
        dir = os.path.dirname(self._cache_path)
        if not os.path.exists(dir):
            os.makedirs(dir, 0o700)
        mode = os.O_WRONLY | os.O_CREAT
        with os.fdopen(os.open(self._cache_path, mode, 0o600), 'wb') as f:
            pickle.dump({
                'messages': self._cache,
                'resolve': self._resolve,
                'index': self._index
            }, f)


class StubFactory(object):
    def __init__(self, mailbox, cache):
        self._mailbox = mailbox
        self._cache = cache

    def __getitem__(self, key):
        try:
            headers = self._cache[self._mailbox.cache_key(key)]
        except KeyError:
            logger.debug('cache miss')
            return self._mailbox[key]
        msg = mailbox.Message()
        msg._headers = headers
        return msg

    def __setitem__(self, key, value):
        self._cache[self._mailbox.cache_key(key)] = value

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


class HeaderUpdaterMixin(object):
    def cache_key(self, key):
        return Cache.pathspec('maildir', (self._path, key))

    def _update_cache(self, key, message):
        self.header_cache[self.cache_key(key)] = message

    def __setitem__(self, key, message):
        super(HeaderUpdaterMixin, self).__getitem__(key, message)
        self._update_cache(key, message)

    def __getitem__(self, key):
        message = super(HeaderUpdaterMixin, self).__getitem__(key)
        self._update_cache(key, message)
        return message
