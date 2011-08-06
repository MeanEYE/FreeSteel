#!/usr/bin/env python

import time
from freesteel.common import get_default_reader
from freesteel.card import CardCommand
from freesteel.eid_card import CardFile, EidCard, PersonalField

# get default reader from system
reader = get_default_reader()

# wait for card insertion
print 'Waiting for card in "{0}"...'.format(reader.name)
card = reader.wait_for_card()

print "Card inserted!"

# assume it's electronic ID
eid_card = EidCard(card)

# get card data
personal = eid_card.get_personal()
photo = eid_card.get_photo()

print 'Card owner is: {0} ({1}) {2}'.format(
										personal[PersonalField.FIRST_NAME], 
										personal[PersonalField.MIDDLE_NAME], 
										personal[PersonalField.LAST_NAME]
									)

# save photo to file
jpeg_file = open('photo.jpg', 'wb+')
jpeg_file.write(photo)
jpeg_file.close()

print 'Photo was saved in: photo.jpg'

card.disconnect()
reader.release_context()
