#!/usr/bin/env python3
import collections
import functools


message = functools.partial(
    collections.namedtuple('Message', ('id', 'subject', 'ref')),
    subject=None,
    ref=[]
)


class Container:
    def __init__(self, message):
        self.message = message
        self._parent = None
        self._children = set()

    @property
    def is_root(self):
        return self._parent is None

    @property
    def is_placeholder(self):
        return self.message.subject is None

    def can_reach(self, other):
        assert self is not other
        if other in self._children:
            return True
        return any(c.can_reach(other) for c in self._children)

    def prune(self):
        newchildren = set()
        for c in self._children:
            assert c._parent is self, '%r not parent of %r' % (self, c)
            newchildren.update(c.prune())
        self._children = newchildren

        if self.is_placeholder:
            if self._parent is None and len(self._children) != 1:
                return [self]

            return newchildren

        return [self]

    def add_child(self, other):
        if self.can_reach(other) or other.can_reach(self):
            #print('would loop %r => %r' % (self, other))
            return
        if other._parent is not None:
            other._parent._children.remove(other)
        self._children.add(other)
        other._parent = self

    def dump(self, print=print, level=0):
        padding = '\t' * level
        if self.is_placeholder:
            print('%s[Placeholder %s]' % (padding, self.message.id))
        else:
            print('%sId: %s' % (padding, self.message.id))
            print('%sSubject: %s' % (padding, self.message.subject))

        for c in self._children:
            c.dump(print, level + 1)

    def __repr__(self):
        return '<Container (of %r)>' % self.message.id


class Table(dict):
    @property
    def root_set(self):
        for v in self.values():
            if v.is_root:
                yield v

    def placeholder(self, message_id):
        return Container(message(message_id))

    def add_message(self, message):
        try:
            container = self[message.id]
            if container.is_placeholder:
                container.message = message
        except KeyError as e:
            container = Container(message)
            self[message.id] = container

        lastc = None
        for ref in message.ref:
            rcontainer = self.setdefault(ref, self.placeholder(ref))
            if lastc is not None:
                lastc.add_child(rcontainer)
            lastc = rcontainer

        if lastc is not None:
            lastc.add_child(container)


def thread(messages):
    table = Table()
    for message in messages:
        table.add_message(message)
    for c in table.root_set:
        nc, = c.prune()
        ## subject merge
        ## sorting
        yield nc
