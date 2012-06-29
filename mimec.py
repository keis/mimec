#!/usr/bin/env python3

import os
import sys
import logging
from email.parser import FeedParser
from email.generator import Generator
from email.message import Message
import email.utils
import mimetypes
import base64

logger = logging.getLogger('mime-compiler')


def get_argparser():
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument('message', nargs='?',
        help='root message')
    parser.add_argument('part', nargs='*',
        help='additional parts')

    parser.add_argument('--debug', action='store_true',
        help='Enable debug logging')
    parser.add_argument('--info', action='store_true',
        help='Write message information instead of entire message')
    parser.add_argument('--attach', metavar='FILE', action='append',
        help='Add attachment')

    # Header modification
    group = parser.add_argument_group('header modification')
    group.add_argument('--subject',
        help='Set subject header on message')
    group.add_argument('--from', dest='_from',
        help='Set from header on message')
    group.add_argument('--to', action='append',
        help='Add recipent of the message')
    group.add_argument('--cc', action='append',
        help='Add carbon copy recipent of the message')

    return parser


class MimeCompiler(object):
    def __init__(self, message=None):
        self._message = message or Message()
        self._last_part = self._message

    def close(self):
        logger.debug('closing message')
        message = self._message
        del self._message
        return message

    def set_from(self, who):
        logger.debug('setting from: %s', who)
        self._message['From'] = who

    def set_subject(self, subject):
        logger.debug('setting subject: %s', subject)
        message = self._message
        del self._message['Subject']
        self._message['Subject'] = subject

    def _add_recipents(self, header, new):
        logger.debug('adding recipent (%s) %r', header, new)
        message = self._message
        recipents = email.utils.getaddresses(message.get_all(header, []))
        rset = set([x[1] for x in recipents])
        for r in new:
            if r not in rset:
                message[header] = r

    def add_to(self, recipents):
        self._add_recipents('To', recipents)

    def add_cc(self, recipents):
        self._add_recipents('Cc', recipents)

    def lift(self):
        '''Lift the message to mime multipart'''

        old = Message()
        old.set_payload(self._message._payload)
        old['Content-Type'] = self._message['Content-Type'] or 'text/plain'
        self._message._payload = [old]
        self._message['Content-Type'] = 'multipart/mixed'

    def attach(self, path, data, mime=None, disposition='attachment'):
        if not self._message.is_multipart():
            self.lift()

        if isinstance(data, Message):
            self._message.attach(data)
            return

        if mime is None:
            mime, enc = mimetypes.guess_type(path)
            mime = mime or 'text/plain'

        name = os.path.basename(path)

        logger.debug('attaching %r as %s', path, mime)
        submessage = Message()
        submessage['Content-Type'] = mime

        binary = mime.startswith('application/') or mime.startswith('image/')

        if disposition == 'attachment' or disposition is None and binary:
            logger.debug('attachment with name %s [%r]', name, path)
            submessage['Content-Disposition'] = 'attachment; filename="%s"' % name

        try:
            ascii = data.decode('ASCII')
            submessage.set_payload(ascii)
        except UnicodeDecodeError:
            enc = base64.b64encode(data).decode('ASCII')
            submessage['Content-Transfer-Encoding'] = 'base64'
            submessage.set_payload(enc)

        self._message.attach(submessage)
        self._last_part = submessage


def read_file(path):
    if path == '-':
        file = sys.stdin
    else:
        file = open(path, mode='rb')

    parser = FeedParser()
    logger.debug('loading %r', file.name)
    with file as f:
        data = f.read()
        try:
            parser.feed(data.decode('utf-8'))
        except UnicodeDecodeError:
            return data
    message = parser.close()
    if len(message._headers) == 0:
        return data
    return message


def dump_message(message):
    generator = Generator(sys.stdout)
    generator.flatten(message)


def main():
    parser = get_argparser()
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(levelname)s %(asctime)-15s [%(funcName)s] - %(message)s'
        )

    parts = args.part
    loaded_parts = []
    message = None

    # Try to load first part as a message if possible
    if args.message:
        m = read_file(args.message)
        if isinstance(m, Message):
            logger.debug('using %r as root message', m)
            message = m
        else:
            loaded_parts.append((args.message, m, None))

    mimec = MimeCompiler(message)

    if args._from:
        mimec.set_from(args._from)

    if args.subject:
        mimec.set_subject(args.subject)

    if args.to:
        mimec.add_to(args.to)

    if args.cc:
        mimec.add_cc(args.cc)

    for part in parts:
        loaded_parts.append((part, read_file(part), None))

    if args.attach:
        for att in args.attach:
            loaded_parts.append((att, read_file(att), 'attachment'))

    for part, data, dis in loaded_parts:
        mimec.attach(part, data=data, disposition=dis)

    message = mimec.close()

    if args.info:
        for part in message.walk():
            for k, v in part.items():
                print('%s: %s' % (k, v))
            ctype = part.get_content_type()
            print('part of type %s' % ctype)
    else:
        dump_message(message)

if __name__ == '__main__':
    main()
