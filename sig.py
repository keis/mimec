#!/usr/bin/env python3
from __future__ import print_function

from collections import defaultdict
from functools import partial


class SignalControl(Exception): pass
class Disconnect(SignalControl): pass
class StopProgagation(SignalControl): pass


class boundsignal(object):
    '''A signal that when published calls all of its subscribers'''

    def __init__(self, signal, im_self):
        self.__signal = signal
        self.__im_self = im_self

        self.subscribe = partial(signal.subscribe, im_self)
        self.disconnect = partial(signal.disconnect, im_self)
        self.publish = partial(signal.publish, im_self)

    def __call__(self, **kwargs):
        self.publish(**kwargs)

    def __repr__(self):
        return '<bound signal of %r>' % (self.__im_self,)


class signal(object):
    '''Publish/Subscribe pattern in a descriptor

        By creating a class member of this type you are enabling the class
        to publish events by that name for others to subscribe too
    '''

    def __init__(self):
        self.__subscribers = defaultdict(list)

    def __get__(self, obj, objtype=None):
        '''Descriptor protocol

            returns self wrapped in a `boundsignal` when accessed from a
            instance
        '''

        if obj is None:
            return self
        return boundsignal(self, obj)

    def subscribe(self, obj, subscriber):
        '''Subscribe a callback to this event'''
        self.__subscribers[obj].append(subscriber)

    def disconnect(self, obj, subscriber):
        '''Disconnect a callback from this event'''
        self.__subscribers[obj].remove(subscriber)

    def publish(self, obj, **kwargs):
        '''Invoke all subscribers to this event

            Two flowcontrol exceptions exist that may be raised by subscribers
             * `Disconnect`
                A subscriber raising this exception will not be notified of
				this event further
             * `StopPropagation`
                Immediatly breaks the publish loop, no other subscribers will
                be notified.

            All other exceptions will be passed to the parent context and will
            break the publish loop without notifing remaining subscribers
        '''
        subscribers = self.__subscribers[obj]
        disconnected = []
        try:
            for sub in subscribers:
                try:
                    sub(**kwargs)
                except Disconnect as e:
                    disconnected.append(sub)
                except StopProgagation:
                    break
        finally:
            for d in disconnected:
                subscribers.remove(d)

    def __call__(self, obj, **kwargs):
        ''' Alias for publish '''
        self.publish(obj)

    def __repr__(self):
        return '<signal at 0x%r>' % id(self)

if __name__ == '__main__':
    class Bar:
        throb = signal()


    class Foo:
        method_two = signal()

        def __init__(self, bar):
            self.__bar = bar
            self.method_one = bar.throb
            bar.throb.subscribe(self.method_two)


    bar = Bar()

    bar.throb.subscribe(partial(print, 'hello '))
    Bar.throb.subscribe(bar, partial(print, 'world!'))

    # prints
    bar.throb()

    # prints too
    f = bar.throb
    f()

    # does not print
    Bar.throb(None)


    foo = Foo(bar)
    foo.method_one.subscribe(partial(print, 'spam'))
    foo.method_two.subscribe(partial(print, 'egg'))

    # prints some more
    bar.throb()
