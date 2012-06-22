def main():
	#testbox = '/home/david.keijser/Mail/gmail/[Google Mail].All Mail'
	testbox = '/home/david.keijser/Mail/gmail/INBOX'

	import mailbox
	from .adapt import read_maildir
	from . import thread
	maildir = mailbox.Maildir(testbox, create=False)
	for c in thread(read_maildir(maildir)):
		c.dump()
		print('****')


if __name__ == '__main__':
	main()
