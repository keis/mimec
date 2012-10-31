import unittest
import sig
from sig import signal, Broker, Disconnect, StopPropagation
import mock


class Source(object):
    spam = signal()


class Mixed(Source, Broker):
    pass


class TestSignals(unittest.TestCase):
    def setUp(self):
        self.listener = mock.Mock()
        self.source = Source()

    def test_calls_subscribed(self):
        sentinel = object()

        self.source.spam.subscribe(self.listener.spam_cb)
        self.source.spam(s=sentinel)
        self.listener.spam_cb.assert_called_once_with(s=sentinel)

    def test_disconnect(self):
        self.source.spam.subscribe(self.listener.spam_cb)
        self.source.spam.subscribe(self.listener.spam2_cb)
        self.source.spam()

        self.source.spam.disconnect(self.listener.spam_cb)
        self.source.spam()
        
        self.assertEqual(1, self.listener.spam_cb.call_count)
        self.assertEqual(2, self.listener.spam2_cb.call_count)

    def test_subscribe_on_bound(self):
        bsignal = self.source.spam
        bsignal.subscribe(self.listener.spam_cb)
        self.source.spam()
        self.listener.spam_cb.assert_called_once_with()

    def test_publish_on_bound(self):
        self.source.spam.subscribe(self.listener.spam_cb)
        bsignal = self.source.spam
        bsignal()
        self.listener.spam_cb.assert_called_once_with()

    def test_disconnect_on_bound(self):
        bsignal = self.source.spam
        self.source.spam.subscribe(self.listener.spam_cb)
        self.source.spam.subscribe(self.listener.spam2_cb)
        self.source.spam()

        bsignal.disconnect(self.listener.spam_cb)
        self.source.spam()
        
        self.assertEqual(1, self.listener.spam_cb.call_count)
        self.assertEqual(2, self.listener.spam2_cb.call_count)

    def test_subscribe_on_static(self):
        Source.spam.subscribe(self.source, self.listener.spam_cb)
        self.source.spam()
        self.listener.spam_cb.assert_called_once_with()

    def test_publish_on_static(self):
        self.source.spam.subscribe(self.listener.spam_cb)
        Source.spam(self.source)
        self.listener.spam_cb.assert_called_once_with()

    def test_disconnect_on_static(self):
        self.source.spam.subscribe(self.listener.spam_cb)
        self.source.spam.subscribe(self.listener.spam2_cb)
        self.source.spam()

        Source.spam.disconnect(self.source, self.listener.spam_cb)
        self.source.spam()
        
        self.assertEqual(1, self.listener.spam_cb.call_count)
        self.assertEqual(2, self.listener.spam2_cb.call_count)

    def test_disconnect_exc(self):
        self.listener.spam_cb = mock.Mock(side_effect=Disconnect)
        self.source.spam.subscribe(self.listener.spam_cb)
        self.source.spam.subscribe(self.listener.spam_cb2)
        self.source.spam()
        self.source.spam()
        self.assertEqual(1, self.listener.spam_cb.call_count)
        self.assertEqual(2, self.listener.spam_cb2.call_count)

    def test_stop_exc(self):
        self.listener.spam_cb = mock.Mock(side_effect=StopPropagation)
        self.source.spam.subscribe(self.listener.spam_cb)
        self.source.spam.subscribe(self.listener.spam_cb2)
        self.source.spam()
        self.assertEqual(1, self.listener.spam_cb.call_count)
        self.assertEqual(0, self.listener.spam_cb2.call_count)


class TestBroker(unittest.TestCase):
    def setUp(self):
        self.listener = mock.Mock()
        self.broker = Broker()

    def test_calls_subscribed(self):
        event = 'test'
        sentinel = object()
        self.broker.subscribe(event, self.listener.test_cb)
        self.broker.publish(event, s=sentinel)
        self.listener.test_cb.assert_called_once_with(s=sentinel)

    def test_disconnect(self):
        event = 'test'
        self.broker.subscribe(event, self.listener.test_cb)
        self.broker.subscribe(event, self.listener.test2_cb)
        self.broker.publish(event)

        self.broker.disconnect(event, self.listener.test_cb)
        self.broker.publish(event)
        
        self.assertEqual(1, self.listener.test_cb.call_count)
        self.assertEqual(2, self.listener.test2_cb.call_count)

    def test_disconnect_exc(self):
        event = 'test'
        self.listener.spam_cb = mock.Mock(side_effect=Disconnect)
        self.broker.subscribe(event, self.listener.spam_cb)
        self.broker.subscribe(event, self.listener.spam_cb2)
        self.broker.publish(event)
        self.broker.publish(event)
        self.assertEqual(1, self.listener.spam_cb.call_count)
        self.assertEqual(2, self.listener.spam_cb2.call_count)

    def test_stop_exc(self):
        event = 'test'
        self.listener.spam_cb = mock.Mock(side_effect=StopPropagation)
        self.broker.subscribe(event, self.listener.spam_cb)
        self.broker.subscribe(event, self.listener.spam_cb2)
        self.broker.publish(event)
        self.assertEqual(1, self.listener.spam_cb.call_count)
        self.assertEqual(0, self.listener.spam_cb2.call_count)


class TestMixed(unittest.TestCase):
    def setUp(self):
        self.listener = mock.Mock()
        self.mixed = Mixed()

    def test_subscribe_signal_publish_broker(self):
        sentinel = object()
        self.mixed.spam.subscribe(self.listener.spam_cb)
        self.mixed.publish(self.mixed.spam, s=sentinel)
        self.listener.spam_cb.assert_called_once_with(s=sentinel)

    def test_subscribe_broker_publish_signal(self):
        sentinel = object()
        self.mixed.subscribe(self.mixed.spam, self.listener.spam_cb)
        self.mixed.spam(s=sentinel)
        self.listener.spam_cb.assert_called_once_with(s=sentinel)
