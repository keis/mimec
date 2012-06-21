#!/usr/bin/env python3
from gi.repository import GObject, Gtk
import os
import mailbox
import json
import xdg
import logging


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('post')


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
        for path, dirnames, files in os.walk(s):
            try:
                maildir = mailbox.Maildir(path, create=False)
            except OSError as e:
                continue

            del dirnames[:]
            name = os.path.split(path)[-1]
            add(miter, [name, path])

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
        self.mailbox = mailbox.Maildir(path, create=False)
        self._storage.clear()
        logger.info('threading %s messages', len(self.mailbox))
        messages = threader.thread(threader.adapt.read_maildir(self.mailbox))
        logger.info('done threading')
        copy(
            messages,
            None
        )

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
        self.mailbox_list = builder.get_object('mailbox-list')
        self.mail = MailList(builder.get_object('mail'))
        self.window = builder.get_object('post-main-window')
        self.show_all = self.window.show_all

        builder.get_object('post-main-window').connect(
            'destroy', self.quit
        )
        builder.get_object('select-mailbox').connect(
            'clicked', self.mailbox_button_clicked
        )
        builder.get_object('mailbox-selection').connect(
            'changed', self.selection_changed
        )

    def load_state(self):
        try:
            with open(self.state_path, 'r') as cfg:
                self.state = json.loads(cfg.read())
        except IOError as e:
            self.state = {}
            logger.info('could not open state file')

    def save_state(self):
        try:
            with open(self.state_path, 'w') as cfg:
                cfg.write(json.dumps(self.state))
        except IOError as e:
            logger.info('could not open state file')

    def init(self):
        if 'mailbox' in self.state:
            self.mailbox_list.hide()
            self.mail.load_mailbox(self.state['mailbox'])
        else:
            self.mailboxes.scan()
            self.populate_mailboxes()

    def quit(self, _window):
        self.save_state()
        Gtk.main_quit()

    def toggle_mailbox_list(self):
        self.mailbox_list.set_visible(not self.mailbox_list.get_visible())

    def mailbox_button_clicked(self, button):
        self.toggle_mailbox_list()
        if len(self.mailboxes) == 0:
            self.mailboxes.scan()

    def selection_changed(self, selector):
        store, iter = selector.get_selected()
        row = store[iter]
        mailbox = row[1]
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
