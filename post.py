#!/usr/bin/env python3
from __future__ import print_function
from gi.repository import GObject, Gtk
import os
import mailbox
import logging
import mcache
from sig import signal
from app import App
from util import defer

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s %(asctime)-15s %(message)s [%(funcName)s]'
)
logger = logging.getLogger(__name__)

app = App('post', {
    'mailboxes': ['~/Mail']
})


class Post(App):
    def __init__(self):
        App.__init__(self, 'post')

    def create_post(self, mailbox_search):
        ui = 'ui/post.glade'

        builder = Gtk.Builder()
        builder.add_from_file(ui)

        builder.get_object('mailboxes').search = mailbox_search
        self.post = builder.get_object('post-main-window')
        self.messages = builder.get_object('messages')

        self.post.connect(
            'destroy', self.quit
        )
        self.post.message_activated.subscribe(
            lambda message_id=None: print("hello %s!" % message_id))
        self.post.message_selected.subscribe(
            lambda message: print('Message from %s: %s' % (
                message['From'],
                message['Subject']
            )))
        self.post.mailbox_changed.subscribe(
            lambda mailbox=None: self.state.__setitem__('mailbox', mailbox))

        return self.post

    def ready(self):
        logger.info('initialising')
        if 'mailbox' in self.state:
            self.post.hide_mailbox_list()
            defer(self.messages.load_mailbox, self.state['mailbox'])
        else:
            self.mailboxes.scan()

    def quit(self, _window):
        self.save_state()
        Gtk.main_quit()


app = Post()


class Maildir(mcache.HeaderUpdaterMixin, mailbox.Maildir):
    header_cache = mcache.Cache(app.xdg.cache('header_cache'))
    try:
        header_cache.load()
    except:
        logger.warn('failed to load cache', exc_info=True)


def load_message(message_id, maildir=None):
    for spec, key in Maildir.header_cache.lookup(message_id):
        if spec != 'maildir':
            continue
        path, key = key
        if maildir is None:
            maildir = Maildir(path, create=False)
        elif maildir._path != path:
            continue
        return maildir[key]
    raise KeyError('Message not found: %s' % message_id)


class MailboxList(Gtk.TreeStore, Gtk.Buildable):
    __gtype_name__ = 'MailboxList'

    def __init__(self):
        self.search = []

    def scan_directory(self, s):
        add = self.append
        miter = add(None, [os.path.split(s)[-1], None])
        logger.info('scanning %s for mailboxes', s)
        for path, dirnames, files in os.walk(s):
            if not os.path.exists(os.path.join(path, 'cur')):
                continue

            del dirnames[:]
            name = os.path.split(path)[-1]
            add(miter, [path, name])
        logger.info('done scanning %s', s)

    def scan(self):
        self.clear()
        for s in self.search:
            self.scan_directory(s)


class MessageList(Gtk.TreeStore, Gtk.Buildable):
    __gtype_name__ = 'MessageList'

    def __init__(self):
        self.mailbox = None

    def load_mailbox(self, path):
        from email.header import decode_header
        import threader.adapt
        add = self.append

        def copy(messages, iter):
            for m in messages:
                if m.message.subject:
                    # NOTE: Reuses the normalized subject from threadr
                    # might not want to do that
                    parts = decode_header(m.message.subject)
                    subject = ''.join(
                        [h[0] if h[1] is None else h[0].decode(h[1]) for h in parts]
                    )
                else:
                    subject = m.message.id
                citer = add(iter, [
                    m.message.id,
                    subject
                ])
                copy(m._children, citer)

        logger.info('loading mailbox: %s', path)
        self.mailbox = Maildir(path, create=False)
        headers = mcache.StubFactory(self.mailbox, self.mailbox.header_cache)
        self.clear()
        logger.info('threading %s messages', len(self.mailbox))
        messages = threader.thread(threader.adapt.read_maildir(headers))
        messages = list(messages)
        logger.info('done threading')
        copy(
            messages,
            None
        )
        Maildir.header_cache.save()


class PostWindow(Gtk.Window, Gtk.Buildable):
    __gtype_name__ = 'PostWindow'

    message_activated = signal()
    message_selected = signal()
    mailbox_selected = signal()
    mailbox_changed = signal()

    messages = GObject.property(type=Gtk.TreeStore)
    message_view = GObject.property(type=Gtk.TreeView)
    message_selection = GObject.property(type=Gtk.TreeSelection)

    mailboxes = GObject.property(type=MailboxList)
    mailbox_button = GObject.property(type=Gtk.Button)
    mailbox_list = GObject.property(type=Gtk.Widget)
    mailbox_selection = GObject.property(type=Gtk.TreeSelection)

    def __init__(self):
        self.mailbox_selected.subscribe(self._change_mailbox)

    def init(self):
        if 'mailbox' in app.state:
            self.hide_mailbox_list()
            defer(self.messages.load_mailbox, app.state['mailbox'])
        else:
            self.mailboxes.scan()

    def do_parser_finished(self, builder):
        self.message_view.connect(
            'row-activated', self._message_row_activated)
        self.message_selection.connect(
            'changed', self._message_selection_changed)
        self.mailbox_button.connect(
            'clicked', self._mailbox_button_clicked)
        self.mailbox_selection.connect(
            'changed', self._mailbox_selection_changed)

    def _message_row_activated(self, treeview, path, col):
        iter = self.messages.get_iter(path)
        message_id = self.messages[iter][0]
        self.message_activated(message_id=message_id)

    def _message_selection_changed(self, selector):
        store, iter = selector.get_selected()
        row = store[iter]
        try:
            message = load_message(row[0], self.messages.mailbox)
        except KeyError as e:
            logger.warning('Could not read message', exc_info=True)
        else:
            self.message_selected(message=message)

    def _mailbox_button_clicked(self, w):
        on = self.toggle_mailbox_list()
        if on and len(self.mailboxes) == 0:
            self.mailboxes.scan()

    def _mailbox_selection_changed(self, selector):
        store, iter = selector.get_selected()
        row = store[iter]
        mailbox = row[0]
        if mailbox is not None:
            self.mailbox_selected(mailbox=mailbox)

    def _change_mailbox(self, mailbox=None):
        self.messages.load_mailbox(mailbox)
        self.mailbox_changed(mailbox=mailbox)

    def toggle_mailbox_list(self):
        state = not self.mailbox_list.get_visible()
        self.mailbox_list.set_visible(state)
        return state

    def hide_mailbox_list(self):
        self.mailbox_list.hide()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mailbox', nargs='*')
    args = parser.parse_args()

    p = Post()
    post = app.create_post(map(os.path.expanduser, args.mailbox or app.config['mailboxes']))
    post.show_all()
    defer(app.ready)
    Gtk.main()
