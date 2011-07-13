import smartcard.scard as scard

from exceptions import GetContextError, GetReaderListError, EmptyReaderListError

context = None


def get_context():
	"""Get context"""
	global context

	# only get context once
	if context is None:
		result, context = scard.SCardEstablishContext(scard.SCARD_SCOPE_USER)
		
		if result != scard.SCARD_S_SUCCESS:
			# failed to get context
			message = scard.SCardGetErrorMessage(result)
			raise GetContextError('Failed to establish context: {0}'.format(message))
			
	return context 

def get_reader_list():
	"""Get list of available readers"""
	result, readers = scard.SCardListReaders(get_context(), [])
	
	if result != scard.SCARD_S_SUCCESS:
		# failed to get reader list
		message = scard.SCardGetErrorMessage(result)
		raise GetReaderListError('Failed to obtain reader list: {0}'.format(message))
	
	elif len(readers) == 0:
		# no readers detected on the system
		raise EmptyReaderListError('No smart card readers detected!')
	
	return readers