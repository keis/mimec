#!/usr/bin/env python3
from gi.repository import GObject, Gtk
import os
import mailbox
import json
import xdg
import logging
import mcache
from sig import signal

logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s %(asctime)-15s %(message)s [%(funcName)s]'
)
logger = logging.getLogger(__name__)


def defer(fun, *args, **kwargs):
    def _wrap():
        fun(*args, **kwargs)
        return False
    GObject.idle_add(_wrap)


class MailboxList:
    def __init__(self, storage, search):
        self._storage = storage
        self._search = search

    def __len__(self):
        return len(self._storage)

    def scan_directory(self, s):
        add = self._storage.append
        miter = add(None, [os.path.split(s)[-1], None])
        logger.info('scanning %s for mailboxes', s)
        for path, dirnames, files in os.walk(s):
            if not os.path.exists(os.path.join(path, 'cur')):
                continue

            del dirnames[:]
            name = os.path.split(path)[-1]
            add(miter, [name, path])
        logger.info('done scanning %s', s)

    def scan(self):
        for s in self._search:
            self.scan_directory(s)


class MailList:
    def __init__(self, storage):
        self._storage = storage
        self.mailbox = None

    def __len__(self):
        return len(self._storage)

    def load_mailbox(self, path):
        import threader.adapt
        add = self._storage.append

        def copy(messages, iter):
            for m in messages:
                citer = add(iter, [m.message.subject or m.message.id])
                copy(m._children, citer)

        logger.info('loading mailbox: %s', path)
        cache = os.path.join(xdg.cache_home, 'post', 'header_cache')
        self.mailbox = mcache.HeaderCached(path, create=False, cache=cache)
        headers = self.mailbox.header_cache
        try:
            headers.load()
        except:
            logger.warn('failed to load cache', exc_info=True)
        self._storage.clear()
        logger.info('threading %s messages', len(self.mailbox))
        messages = threader.thread(threader.adapt.read_maildir(headers))
        messages = list(messages)
        logger.info('done threading')
        copy(
            messages[:100],
            None
        )
        headers.save()


class MailboxesWidget:
    selection_changed = signal()

    def __init__(self, mailboxes, button, list, selection):
        self.mailboxes = mailboxes
        self._button = button
        self._list = list
        self._selection = selection

        self._button.connect('clicked', self._button_clicked)
        self._selection.connect('changed', self._selection_changed)

    def _button_clicked(self, w):
        on = self.toggle()
        if on and len(self.mailboxes) == 0:
            self.mailboxes.scan()

    def _selection_changed(self, selector):
        store, iter = selector.get_selected()
        row = store[iter]
        mailbox = row[1]
        if mailbox is not None:
            self.selection_changed(mailbox=mailbox)

    def toggle(self):
        state = not self._list.get_visible()
        self._list.set_visible(state)
        return state

    def hide(self):
        self._list.hide()


class Post:
    ui = 'ui/post.glade'
    state_path = os.path.join(xdg.config_home, 'post', 'state')

    def __init__(self, mailbox_search):
        self.mailbox_search = mailbox_search
        builder = Gtk.Builder()
        builder.add_from_file(self.ui)

        self.mailboxes = MailboxList(
            builder.get_object('mailboxes'),
            mailbox_search
        )
        self.mailboxeswidget = MailboxesWidget(
            self.mailboxes,
            builder.get_object('select-mailbox'),
            builder.get_object('mailbox-pane'),
            builder.get_object('mailbox-selection')
        )
        self.mailboxeswidget.selection_changed.subscribe(self._change_mailbox)
        self.mail = MailList(builder.get_object('mail'))
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
            defer(self.mail.load_mailbox, self.state['mailbox'])
        else:
            self.mailboxes.scan()

    def quit(self, _window):
        self.save_state()
        Gtk.main_quit()

    def _change_mailbox(self, mailbox=None):
        self.mail.load_mailbox(mailbox)
        self.state['mailbox'] = mailbox

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('mailbox', nargs='+')
    args = parser.parse_args()

    p = Post(args.mailbox)
    p.load_state()
    p.show_all()
    defer(p.init)
    Gtk.main()
