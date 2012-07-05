#!/usr/bin/env python3
from gi.repository import GObject, Gtk
import os
import mailbox
import json
import xdg
import logging
import mcache
from sig import signal

XDG = xdg.Context('post')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s %(asctime)-15s %(message)s [%(funcName)s]'
)
logger = logging.getLogger(__name__)


class Maildir(mcache.HeaderUpdaterMixin, mailbox.Maildir):
    header_cache = mcache.Cache(XDG.cache('header_cache'))


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


def defer(fun, *args, **kwargs):
    def _wrap():
        fun(*args, **kwargs)
        return False
    GObject.idle_add(_wrap)


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
    selection = GObject.property(type=Gtk.TreeSelection)

    def __init__(self):
        self.mailbox = None

    def do_parser_finished(self, builder):
        self.selection.connect('changed', self._selection_changed)

    def _selection_changed(self, selector):
        # PLACEHOLDER
        store, iter = selector.get_selected()
        row = store[iter]
        try:
            message = load_message(row[0], self.mailbox)
        except KeyError as e:
            print(e)
        else:
            print('Message from <%s>: %s' % (message['From'], message['Subject']))

    def load_mailbox(self, path):
        import threader.adapt
        add = self.append

        def copy(messages, iter):
            for m in messages:
                citer = add(iter, [
                    m.message.id,
                    m.message.subject or m.message.id
                ])
                copy(m._children, citer)

        logger.info('loading mailbox: %s', path)
        self.mailbox = Maildir(path, create=False)
        headers = mcache.StubFactory(self.mailbox, self.mailbox.header_cache)
        try:
            headers.load()
        except:
            logger.warn('failed to load cache', exc_info=True)
        self.clear()
        logger.info('threading %s messages', len(self.mailbox))
        messages = threader.thread(threader.adapt.read_maildir(headers))
        messages = list(messages)
        logger.info('done threading')
        copy(
            messages,
            None
        )
        headers.save()


class MailboxesWidget(GObject.GObject, Gtk.Buildable):
    __gtype_name__ = 'MailboxesWidget'
    selection_changed = signal()
    mailboxes = GObject.property(type=MailboxList)
    button = GObject.property(type=Gtk.Button)
    list = GObject.property(type=Gtk.Widget)
    selection = GObject.property(type=Gtk.TreeSelection)

    def do_parser_finished(self, builder):
        self.button.connect('clicked', self._button_clicked)
        self.selection.connect('changed', self._selection_changed)

    def _button_clicked(self, w):
        on = self.toggle()
        if on and len(self.mailboxes) == 0:
            self.mailboxes.scan()

    def _selection_changed(self, selector):
        store, iter = selector.get_selected()
        row = store[iter]
        mailbox = row[0]
        if mailbox is not None:
            self.selection_changed(mailbox=mailbox)

    def toggle(self):
        state = not self.list.get_visible()
        self.list.set_visible(state)
        return state

    def hide(self):
        self.list.hide()


class MessageWidget(GObject.GObject, Gtk.Buildable):
    __gtype_name__ = 'MessageWidget'
    messages = GObject.property(type=Gtk.TreeStore)
    message_view = GObject.property(type=Gtk.TreeView)
    message_activated = signal()

    def do_parser_finished(self, builder):
        self.message_view.connect('row-activated', self._row_activated)

    def _row_activated(self, treeview, path, col):
        iter = self.messages.get_iter(path)
        message_id = self.messages[iter][0]
        self.message_activated(message_id=message_id)


class Post:
    ui = 'ui/post.glade'
    state_path = XDG.config('state')

    def __init__(self, mailbox_search):
        self.mailbox_search = mailbox_search
        builder = Gtk.Builder()
        builder.add_from_file(self.ui)

        builder.get_object('mailboxes').search = mailbox_search
        self.mailboxeswidget = builder.get_object('mailboxes-widget')
        self.mailboxeswidget.selection_changed.subscribe(self._change_mailbox)
        self.messageswidget = builder.get_object('messages-widget')
        self.messageswidget.message_activated.subscribe(self._open_message)
        self.messages = builder.get_object('messages')
        self.show_all = builder.get_object('post-main-window').show_all

        builder.get_object('post-main-window').connect(
            'destroy', self.quit
        )

    def load_state(self):
        try:
            with open(self.state_path, 'r') as cfg:
                self.state = json.loads(cfg.read())
        except IOError:
            self.state = {}
            logger.info('could not open state file')

    def save_state(self):
        try:
            with open(self.state_path, 'w') as cfg:
                cfg.write(json.dumps(self.state))
        except IOError:
            logger.info('could not open state file')

    def init(self):
        if 'mailbox' in self.state:
            self.mailboxeswidget.hide()
            defer(self.messages.load_mailbox, self.state['mailbox'])
        else:
            self.mailboxes.scan()

    def quit(self, _window):
        self.save_state()
        Gtk.main_quit()

    def _change_mailbox(self, mailbox=None):
        self.messages.load_mailbox(mailbox)
        self.state['mailbox'] = mailbox

    def _open_message(self, message_id=None):
        print("hello %s!" % message_id)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mailbox', nargs='*')
    args = parser.parse_args()

    with open(XDG.config('config')) as f:
        config = json.loads(f.read())

    p = Post(map(os.path.expanduser, args.mailbox or config['mailboxes']))
    p.load_state()
    p.show_all()
    defer(p.init)
    Gtk.main()
