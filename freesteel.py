#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# FreeSteel 0.2
#
# Copyright (c) 2010 Goran Rakic <grakic@devbase.net>.
#
# A cross-platform Python script built on top of pyscard and PC/SC to read
# public data of the Serbian national eID card
#
# FreeSteel is free software: you can redistribute it and/or modify it under
# the terms of the Lesser GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# FreeSteel is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the Lesser GNU General Public License for more
# details.
#
# You should have received a copy of the Lesser GNU General Public License along
# with FreeSteel. If not, see <http://www.gnu.org/licenses/>.
#

from smartcard.scard import *
import smartcard.util
import sys, os, getopt, string

VERSION = "0.2"

def usage():
  print """
FreeSteel %s - read data of the Serbian national eID card
Copyright (c) 2010 Goran Rakic <grakic@devbase.net>.

A cross-platform and free Python script built on top of pyscard and PC/SC.
Released under the GNU LGPL license version 3  or (at your option) any later.

Usage: %s [option]... where option can be one of:

  -p, --photo[=FILENAME]    Copy the photo of the smart card. If the filename
                            is not specified, <JMBG>.jpg will be used

  -r, --report[=FILENAME]   Create the PDF report with all data including the
                            photo. If the filename is not specified, <JMBG>.pdf
                            will be used (THE FEATURE IS NOT IMPLEMENTED!)

  -d, --dump=DIRECTORY      Dump EF binary data into the directory
  -v, --verbose             Output sent and received data to stderr

      --help                Display this message
      --version             Output version number


Report bugs to grakic@devbase.net. See the README file for more information
how you can help test and improve FreeSteel.
""" % (VERSION, sys.argv[0])


def create_context():
  hresult, hcontext = SCardEstablishContext(SCARD_SCOPE_USER)
  if hresult != SCARD_S_SUCCESS:
    raise Exception('Failed to establish context : ' + SCardGetErrorMessage(hresult))
  return hcontext

def release_context(hcontext):
  hresult = SCardReleaseContext(hcontext)
  if hresult != SCARD_S_SUCCESS:
    raise Exception('Failed to release context: ' + SCardGetErrorMessage(hresult))

def list_readers(hcontext):
  hresult, readers = SCardListReaders(hcontext, [])
  if hresult != SCARD_S_SUCCESS:
    raise Exception('Failed to list readers: ' + SCardGetErrorMessage(hresult))
  if len(readers) < 1:
    raise Exception('No smart card readers')
  return readers

def card_connect(hcontext, reader):
  hresult, hcard, dwActiveProtocol = SCardConnect(hcontext, reader, SCARD_SHARE_SHARED, SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1)
  if hresult != SCARD_S_SUCCESS:
    raise Exception('Unable to connect: ' + SCardGetErrorMessage(hresult))
  return hcard, dwActiveProtocol

def card_disconnect(hcard):
  hresult = SCardDisconnect(hcard, SCARD_UNPOWER_CARD)
  if hresult != SCARD_S_SUCCESS:
    raise Exception('Failed to disconnect: ' + SCardGetErrorMessage(hresult))

# APDU commands for Serbian eID
cmd = {
  'GET_DATA_0101'   : [0x00, 0xCA, 0x01, 0x01, 0x20], # > GET_DATA_0101
  'SELECT_FILE_PATH': [0x00, 0xA4, 0x08, 0x00],       # > SELECT_FILE_PATH, file_path
  'READ_BINARY'     : [0x00, 0xB0]                    # > READ_BINARY, 2 bytes byte_offset, byte_length
}

def card_transmit(hcard, dwActiveProtocol, *data):
  request = []
  for d in data:
    request.extend(d)

  if debug: print ">", smartcard.util.toHexString(request)
  hresult, response = SCardTransmit(hcard, dwActiveProtocol, request)
  if hresult != SCARD_S_SUCCESS:
    raise Exception('Failed to transmit: ' + SCardGetErrorMessage(hresult))

  if debug: print "<", smartcard.util.toHexString(response)

  # Check for 0x90 0x00 (all OK) confirmation
  check = response[len(response)-2:]
  if check != [0x90, 0x00]:
    raise Exception('Request error: Returned ' + smartcard.util.toHexString(check))

  return response[:-2]

def eid_read_ef(hcard, dwActiveProtocol, ef_path):
  # select, ignore security info reply (read 1byte + 0x90 0x00)
  card_transmit(hcard, dwActiveProtocol, cmd['SELECT_FILE_PATH'], ef_path, [0x01])

  # read first 6 bytes to get ef len as 16bit LE integer at 4B offset
  r = card_transmit(hcard, dwActiveProtocol, cmd['READ_BINARY'], [0x00, 0x00, 0x06])
  #print r
  ef_len = r[4]+r[5]*256 + 6

  data = []
  ef_off = 6
  while ef_off < ef_len:
    limit = ef_len - ef_off
    if limit > 0xff: limit = 0xff
    data.extend(card_transmit(hcard, dwActiveProtocol, cmd['READ_BINARY'], [ef_off>>8, ef_off&0xff, limit]))
    ef_off += limit

  if dump:
    filename = "ef_%s.bin" % smartcard.util.toHexString(ef_path).replace(' ', '_')
    dump_bin_string(os.path.join(dump, filename), data)

  return data

def eid_split_fields(data):
  flabels = []
  fdata = []
  
  # [fld] [06] [len] [00] [len bytes of data] | [fld] [06] ...
  i = 0
  while i < len(data):
    flabels.append(data[i])
    length = data[i+2]
    fdata.append(data[i+4:i+4+length])
    i += 4+length
  return fdata, flabels

def cli_select_widget(list, title):
  c = 0
  if len(list) > 1:
    print title
    for l in list:
      print "%d) %s" % (c+1, list[c])
      c += 1
    while True:
      c = int(raw_input("Select number:"))
      if c > 0 and c <= len(list):
        c -= 1
        break
  return list[c]

def select_reader(hcontext):
  readers = list_readers(hcontext)
  reader = cli_select_widget(readers, "Available readers")
  print "Using reader   :", reader
  return reader

def dump_bin_string(filename, data):
  f = open(filename, "wb+")
  f.write(''.join([chr(b) for b in data]))
  f.close()

dump = None
debug = False
photo = False;  photo_filename = None
report = False; report_filename = None

def read_options():
  global dump, debug, photo, photo_filename, report, report_filename

  try:
    opts, args = getopt.getopt(sys.argv[1:], "prd:v", ["photo", "report", "dump=", "verbose", "help", "version"])
  except getopt.GetoptError, err:
    print >> sys.stderr, str(err)
    usage()
    sys.exit(2)

  for o, a in opts:
    if o == "-v":
      debug = True
    elif o in ("-d", "--dump"):
      dump = a
      if not os.path.exists(dump):
        os.makedirs(dump)
    elif o in ("-h", "--help"):
      usage()
      sys.exit()
    elif o ==  "--version":
      print "FreeSteel", VERSION
      sys.exit()
    elif o in ("-p", "--photo"):
      photo = True
      photo_filename = a
    elif o in ("-r", "--report"):
      report = True
      report_filename = a
      print >> sys.stderr, "PDF report feature is not implemented"
      sys.exit(3)

def b2a(bytes):
  return smartcard.util.toASCIIString(bytes)

def b2u(bytes):
  return unicode(smartcard.util.toASCIIString(bytes), "utf-8")

def main():

  read_options()

  hcontext = create_context()
  reader = select_reader(hcontext)

  try:
    hcard, dwActiveProtocol = card_connect(hcontext, reader)

    try:

      # Get card's Answer To Reset (not required)
      hresult, n, n, n, atr = SCardStatus(hcard)
      if hresult != SCARD_S_SUCCESS:
        raise Exception('Failed to get ATR: ' + SCardGetErrorMessage(hresult))
      print "ATR            :", smartcard.util.toHexString(atr)
      
      # Start communication, send GET DATA header
      r = card_transmit(hcard, dwActiveProtocol, cmd['GET_DATA_0101'])
      header = smartcard.util.toHexString(r, smartcard.util.PACK)
      print "Header field   :", header
      print "Printed number :", " "*17, header[18:32]

      # Select ef_02_0f_02
      data = eid_read_ef(hcard, dwActiveProtocol, [0x02, 0x0F, 0x02])
      fdata, flabels = eid_split_fields(data)
      print "eID number     :", b2a(fdata[0])
      print "Issued         :", b2a(fdata[3])
      print "Valid          :", b2a(fdata[4])
      print "Issuer         :", b2u(fdata[5]), b2a(fdata[6])

      # Select ef_02_0f_03
      data = eid_read_ef(hcard, dwActiveProtocol, [0x02, 0x0F, 0x03])
      fdata, flabels = eid_split_fields(data)
      jmbg = b2a(fdata[0])
      print "JMBG           :", jmbg
      print "Family name    :", b2u(fdata[1])
      print "First name     :", b2u(fdata[2])
      print "Middle name    :", b2u(fdata[3])
      print "Gender         :", b2u(fdata[4])
      print "Place od birth :", "%s, %s, %s, %s" % (b2u(fdata[5]), b2u(fdata[6]), b2u(fdata[7]), b2u(fdata[9]))
      print "Date of birth  :", b2a(fdata[8])

      # Select ef_02_0f_04
      data = eid_read_ef(hcard, dwActiveProtocol, [0x02, 0x0F, 0x04])
      fdata, flabels = eid_split_fields(data)

      residence  = "%s, %s, %s" % (b2u(fdata[1]), b2u(fdata[2]), b2u(fdata[0]))
      if len(fdata) > 3:
        residence = string.join([b2u(d) for d in fdata[3:]], ', ')+"\n"+" "*17+residence
      print "Residence      :", residence

      if photo or dump:
        # Select ef_02_0f_06
        data = eid_read_ef(hcard, dwActiveProtocol, [0x02, 0x0F, 0x06])

      if photo:
        if not photo_filename:
          filename = jmbg+".jpg"
        else:
          filename = photo_filename
        f = open(filename, "wb+")
        f.write(b2a(data[4:]))
        f.close()

    finally:
      card_disconnect(hcard)

  finally:
    release_context(hcontext)

#  except Exception, message:
#    print >> sys.stderr, "Error:", message
#    raise message

if __name__ == "__main__":
  main()

