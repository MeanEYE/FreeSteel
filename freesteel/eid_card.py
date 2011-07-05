import smartcard


class CardFile:
	DOCUMENT = (0x0F, 0x02)  # Document data
	PERSONAL = (0x0F, 0x03)  # Personal data
	RESIDENCE = (0x0F, 0x04)  # Place of residence, variable length
	PHOTO = (0x0F, 0x06)  # Personal photo in JPEG format
	CERT_QUALIFIED = (0x0F, 0x10)  # Public X.509 certificate for qualified (Non Repudiation) signing
	CERT_STANDARD = (0x0F, 0x08)  # Public X.509 certificate for standard signing
	

class CardCommand:
	GET_DATA_0101 = (0x00, 0xCA, 0x01, 0x01, 0x20)  # GET_DATA_0101
	SELECT_FILE_PATH = (0x00, 0xA4, 0x08, 0x00)  # SELECT_FILE_PATH, file_path_len, file_path bytes...
	READ_BINARY = (0x00, 0xB0)  # READ_BINARY, 2 bytes byte_offset, byte_length


class EidCard:
	"""Wrapper class used for reading electronic ID cards"""
	
	def __init__(self):
		pass