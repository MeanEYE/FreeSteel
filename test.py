#!/usr/bin/env python

import time
from freesteel.common import get_default_reader

def got_card(reader, card):
	global can_continue
	
	# print information
	print "Card inserted in '{0}': {1}".format(reader.name, card)
	
	# stop looping
	can_continue = False

reader = get_default_reader()
reader.wait_for_card_async(got_card)

can_continue = True 

while can_continue:
	print 'Idle...'
	time.sleep(2)

reader.release_context()