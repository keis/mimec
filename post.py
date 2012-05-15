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


class Post:
    ui = 'ui/post.glade'
    state_path = os.path.join(xdg.config_home, 'post', 'state')

    def __init__(self, mailbox_search):
        self.mailbox_search = mailbox_search
        builder = Gtk.Builder()
        builder.add_from_file(self.ui)
        builder.connect_signals(self)
        self.mailboxes = builder.get_object('mailboxes')
        self.mailbox_list = builder.get_object('mailbox-list')
        self.mail = builder.get_object('mail')
        self.window = builder.get_object('post-main-window')
        self.show_all = self.window.show_all

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
            self.select_mailbox(self.state['mailbox'])
        else:
            self.populate_mailboxes()

    def quit(self, _window):
        self.save_state()
        Gtk.main_quit()

    def toggle_mailbox_list(self):
        self.mailbox_list.set_visible(not self.mailbox_list.get_visible())

    def populate_mailboxes(self):
        model = self.mailboxes
        for s in self.mailbox_search:
            miter = model.append(None, [os.path.split(s)[-1], None])
            for path, dirnames, files in os.walk(s):
                try:
                    maildir = mailbox.Maildir(path, create=False)
                except OSError as e:
                    continue

                del dirnames[:]
                name = os.path.split(path)[-1]
                model.append(miter, [name, path])

    def mailbox_button_clicked(self, button):
        self.toggle_mailbox_list()
        if len(self.mailboxes) == 0:
            self.populate_mailboxes()

    def select_mailbox(self, path):
        import threader.adapt
        model = self.mail

        def copy(messages, iter):
            for m in messages:
                print('message', m.message.subject, iter)
                citer = model.append(iter, [m.message.subject or m.message.id])
                copy(m._children, citer)

        logger.info('selecting mailbox: %s', path)
        self.state['mailbox'] = path
        maildir = mailbox.Maildir(path, create=False)
        messages = list(threader.adapt.read_maildir(maildir))
        messages = threader.thread(messages)
        model.clear()
        copy(messages, None)

    def selection_changed(self, selector):
        store, iter = selector.get_selected()
        row = store[iter]
        mailbox = row[1]
        self.select_mailbox(mailbox)

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
