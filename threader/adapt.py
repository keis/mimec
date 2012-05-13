from . import message
import re

_message_id = re.compile('(<[^>]+>)')
def extract_references(mail):
	references = []
	if 'References' in mail:
		refs = _message_id.findall(mail['References'])
		references.extend(refs)
	if 'In-Reply-To' in mail:
		rto = _message_id.match(mail['In-Reply-To'])
		if rto is not None:
			references.append(rto.group(1))
	rset = set()
	return [rset.add(r) or r for r in references if r not in rset]


_normalise_subject = re.compile('^((Re|Sv): )?(.*)').match
def normalise_subject(subject):
	if subject is None:
		return ''
	return _normalise_subject(str(subject)).group(3)


def read_maildir(maildir):
	for mail in maildir:
		message_id = mail['Message-Id']
		references = extract_references(mail)
		subject = normalise_subject(mail['Subject'])

		yield message(
			id=message_id,
			subject=subject,
			ref=references
		)
