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


class App:
    def __init__(self):
        self.config = {
            'mailboxes': ['~/Mail']
        }
        self.state = {}
        self.load_config()
        self.load_state()

    def load_config(self):
        try:
            with open(XDG.config('config')) as f:
                self.config.update(json.loads(f.read()))
        except IOError:
            logger.info('could not read config file')

    def load_state(self):
        try:
            with open(XDG.config('state'), 'r') as cfg:
                self.state.update(json.loads(cfg.read()))
        except IOError:
            self.state = {}
            logger.info('could not open state file')

    def save_state(self):
        try:
            with open(XDG.config('state'), 'w') as cfg:
                cfg.write(json.dumps(self.state))
        except IOError:
            logger.info('could not open state file')

app = App()


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

    def __init__(self):
        self.mailbox = None

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


class PostWindow(Gtk.Window, Gtk.Buildable):
    __gtype_name__ = 'PostWindow'

    message_activated = signal()
    message_selected = signal()
    mailbox_selected = signal()

    messages = GObject.property(type=Gtk.TreeStore)
    message_view = GObject.property(type=Gtk.TreeView)
    message_selection = GObject.property(type=Gtk.TreeSelection)

    mailboxes = GObject.property(type=MailboxList)
    mailbox_button = GObject.property(type=Gtk.Button)
    mailbox_list = GObject.property(type=Gtk.Widget)
    mailbox_selection = GObject.property(type=Gtk.TreeSelection)

    def __init__(self):
        self.mailbox_selected.subscribe(self._change_mailbox)
        self.message_activated.subscribe(self._open_message)
        self.message_selected.subscribe(
            lambda message: print('Message from %s: %s' % (
                message['From'],
                message['Subject']
            )))

    def init(self):
        if 'mailbox' in app.state:
            self.post.hide_mailbox_list()
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
        app.state['mailbox'] = mailbox

    def _open_message(self, message_id=None):
        print("hello %s!" % message_id)

    def toggle_mailbox_list(self):
        state = not self.mailbox_list.get_visible()
        self.mailbox_list.set_visible(state)
        return state

    def hide_mailbox_list(self):
        self.mailbox_list.hide()


class Post:
    ui = 'ui/post.glade'

    def __init__(self, mailbox_search):
        self.mailbox_search = mailbox_search
        builder = Gtk.Builder()
        builder.add_from_file(self.ui)

        builder.get_object('mailboxes').search = mailbox_search
        self.post = builder.get_object('post-main-window')
        self.messages = builder.get_object('messages')
        self.show_all = self.post.show_all

        self.post.connect(
            'destroy', self.quit
        )

    def init(self):
        self.post.init()

    def quit(self, _window):
        app.save_state()
        Gtk.main_quit()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mailbox', nargs='*')
    args = parser.parse_args()

    p = Post(map(os.path.expanduser, args.mailbox or app.config['mailboxes']))
    p.show_all()
    defer(p.init)
    Gtk.main()
