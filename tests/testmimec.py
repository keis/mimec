import unittest
import mimec
from email.message import Message
from email.parser import FeedParser


def mail(data):
    parser = FeedParser()
    parser.feed(data)
    return parser.close()


def envelope(message):
    return {
        'from': str(message.get_all('From')),
        'to': str(message.get_all('To')),
        'subject': str(message.get_all('Subject'))
    }


class TestMimeCompiler(unittest.TestCase):
    def test_lift(self):
        message = mail('''from: john doe <john@inter.net>
to: tiffany <breakfast@tiffany.com>
subject: Hello

this is plain message''')
        e = envelope(message)
        p = message.get_payload()

        m = mimec.MimeCompiler(message)
        m.lift()
        message = m.close()
        self.assertEqual(e, envelope(message))
        self.assertTrue(message.is_multipart())
        self.assertEqual('multipart/mixed', message.get_content_type())

        root, wrapped = list(message.walk())
        self.assertIs(root, message)

        self.assertEqual('text/plain', wrapped.get_content_type())
        self.assertEqual(p, wrapped.get_payload())

    def test_add_to(self):
        m = mimec.MimeCompiler(Message())

        to = ['spam <spam@greenmidget.com>', 'egg@greenmidget.com']
        m.add_to(to)
        message = m.close()
        self.assertEqual(to, message.get_all('To'))

    def test_add_to_duplicate(self):
        message = mail('''from: announcer@gc.gov
to: <harold@onetwo.com>, Bobby <bob@theotherdomain.net>
To: <someone@else.org>
subject: Announcement from genetic control

This is a announcement from genetic control. It is my sad duty to inform you
of a four foot restriction, on humanoid hight
''')
        m = mimec.MimeCompiler(message)
        m.add_to(['bob@theotherdomain.net', 'Bobby <notbob@theotherdomain.net>'])
        message = m.close()
        self.assertEqual([
            '<harold@onetwo.com>, Bobby <bob@theotherdomain.net>',
            '<someone@else.org>',
            'Bobby <notbob@theotherdomain.net>'
        ], message.get_all('To'))
