from reader import Reader


def get_reader_list():
	"""Get list of available readers"""
	return Reader.get_list()

def get_default_reader():
	"""Get default reader"""
	result = None
	readers = get_reader_list()
	
	if len(readers) > 0:
		result = Reader(readers[0])
	
	return result
