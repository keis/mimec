from __future__ import print_function
import sys

try:
    import gevent
    spawn = gevent.spawn
    joinall = gevent.joinall
except ImportError:
    # Mocked gevent
    from collections import namedtuple
    gevent = False
    job = namedtuple('job', ('value'))
    spawn = lambda f, *args, **kwargs: job(f(*args, **kwargs))
    joinall = lambda jobs: None

def main():
    quit = False

    def say(str):
        while not quit:
            print(str, file=sys.stderr)
            gevent.sleep(1)

    def thread_maildir(maildir):
        threaded = thread(read_maildir(maildir))
        print('done threading %s' % maildir._path, file=sys.stderr)
        return threaded

    import os.path
    maildir = os.path.expanduser('~/Mail')

    testboxes = [
        '/home/davve/Mail/klarna/vacation.2012-mar',
        '/home/davve/Mail/gmail/INBOX',
    ]

    import mailbox
    from .adapt import read_maildir
    from . import thread

    if gevent:
        spawn(say, 'tick')

    maildirs = [mailbox.Maildir(box, create=False) for box in testboxes]
    jobs = [spawn(thread_maildir, maildir) for maildir in maildirs]
    joinall(jobs)
    quit = True
    for job in jobs:
        for root in job.value:
            root.dump()


if __name__ == '__main__':
    main()
