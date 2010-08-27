#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# FreeSteel 0.3
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

VERSION = "0.3"

def usage():
  print """
FreeSteel %s - read data of the Serbian national eID card
Copyright (c) 2010 Goran Rakic <grakic@devbase.net>.

A cross-platform and a free Python script built on top of pyscard and PC/SC.
Released under the GNU LGPL license version 3  or (at your option) any later.

Usage: %s [option]... where option can be one of:

  -r --report[=FILE]       Create the PDF report with personal data and photo
                           If the filename is not specified, <JMBG>.pdf will be
                           used. (THE FEATURE IS NOT IMPLEMENTED!)

     --silent              Do not output data on screen
                           Use this to just extract files to a given filename
                           without reading other data from the eID card.


  Extract files options

  -p --photo[=FILE]        Copy the photo of the smart card
                           Default filename is <JMBG>.jpg where JMBG is personal
                           JMBG number read from the eID card.

  -q --qualified[=FILE]    Extract qualified public personal X.509 certificate
                           Default filename is <JMBG>_qualified.cer where JMBG
                           is personal JMBG number read from the eID card.

  -s --standard[=FILE]     Extract standard public personal X.509 certificate
                           Default filename is <JMBG>_standard.cer where JMBG
                           is personal JMBG number read from the eID card.


  Debug and informational options

  -d --dump=DIRECTORY      Dump binary EF data into the directory
  -v --verbose             Output sent and received data to stderr

     --help                Display this message
     --version             Output version number


Report bugs to grakic@devbase.net. See the README file for more information how
you can help test and improve FreeSteel.
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

# APDU commands for the Serbian eID
cmd = {
  'GET_DATA_0101'   : [0x00, 0xCA, 0x01, 0x01, 0x20], # > GET_DATA_0101
  'SELECT_FILE_PATH': [0x00, 0xA4, 0x08, 0x00],       # > SELECT_FILE_PATH, file_path_len, file_path bytes...
  'READ_BINARY'     : [0x00, 0xB0]                    # > READ_BINARY, 2 bytes byte_offset, byte_length
}

# EF files available on the Serbian eID
files = {
  'DOCUMENT'  : [0x0F, 0x02],   # Document data
  'PERSONAL'  : [0x0F, 0x03],   # Personal data
  'RESIDENCE' : [0x0F, 0x04],   # Place of residence, variable length
  'PHOTO'     : [0x0F, 0x06],   # Personal photo in JPEG format
  'QUALIFIED' : [0x0F, 0x08],   # Public X.509 certificate for qualified signing
  'STANDARD'  : [0x0F, 0x10]    # Public X.509 certificate for standard signing
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

  # Check for 0x90 0x00 (all OK) confirmation in response
  check = response[len(response)-2:]
  if check != [0x90, 0x00]:
    raise Exception('Request error: Returned ' + smartcard.util.toHexString(check))

  return response[:-2]

def eid_read_ef(hcard, dwActiveProtocol, ef_path, dump_directory = None):
  # select, ignore security info reply (read 1byte + 0x90 0x00)
  card_transmit(hcard, dwActiveProtocol, cmd['SELECT_FILE_PATH'], [len(ef_path)], ef_path, [0x01])

  # read first 6 bytes to get ef len as 16bit LE integer at 4B offset
  header = card_transmit(hcard, dwActiveProtocol, cmd['READ_BINARY'], [0x00, 0x00, 0x06])

  # FIXME: empty efs have all FF bytes, including header. Probably the empty EF is signaled
  # in SELECT FILE PATH response (up to 32 bytes) but this will work as a quickfix.
  if header == [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]:
    return []

  # FIXME: Missing header? Probably non existing ef or no permissions to read. Again, a quickfix
  if len(header) < 6:
    raise Exception('Request error: Could not read header from EF path ' + smartcard.util.toHexString(ef_path))
  
  # Total EF length: data as 16bit LE at 4B offset + 6 bytes header
  ef_len = (header[5]<<8) + header[4] + 6

  data = []
  ef_off = 6
  while ef_off < ef_len:
    limit = ef_len - ef_off
    if limit > 0xff: limit = 0xff
    data.extend(card_transmit(hcard, dwActiveProtocol, cmd['READ_BINARY'], [ef_off>>8, ef_off&0xff, limit]))
    ef_off += limit

  if dump_directory:
    filename = "ef_%s.bin" % smartcard.util.toHexString(ef_path).replace(' ', '_')
    dump_bin_string(os.path.join(dump_directory, filename), header+data)

  return data

def eid_data_split_fields(data):
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

def eid_data_extract_file(data, filename):
  f = open(filename, "wb+")
  f.write(b2a(data[4:]))
  f.close()

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

dump_directory = None
debug = False; silent = False
report = False; report_filename = None
photo = False;  photo_filename = None
qualified = False; qualified_filename = None
standard = False; standard_filename = None

def read_options():
  global dump_directory, debug, silent, report, report_filename
  global photo, photo_filename, qualified, qualified_filename, standard, standard_filame

  try:
    opts, args = getopt.getopt(sys.argv[1:], "rpqsd:v", ["report", "photo", "qualified", "standard", "silent", "dump=", "verbose", "help", "version"])
  except getopt.GetoptError, err:
    print >> sys.stderr, str(err)
    usage()
    sys.exit(2)

  for o, a in opts:
    if o in ("-v", "--verbose"):
      debug = True
    elif o == "--silent":
      silent = True
    elif o in ("-d", "--dump"):
      dump_directory = a
      if not os.path.exists(dump_directory):
        os.makedirs(dump_directory)
    elif o in ("-h", "--help"):
      usage()
      sys.exit()
    elif o ==  "--version":
      print "FreeSteel", VERSION
      sys.exit()
    elif o in ("-p", "--photo"):
      photo = True
      photo_filename = a
    elif o in ("-q", "--qualified"):
      qualified = True
      qualified_filename = a
    elif o in ("-s", "--standard"):
      standard = True
      standard_filename = a
    elif o in ("-r", "--report"):
      report = True
      report_filename = a
      print >> sys.stderr, "PDF report feature is not implemented"
      sys.exit(3)

  if silent and debug:
    print >> sys.stderr, "I do not know yet how to be both silent and verbose"
    sys.exit(2)

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

      if debug:
        # Get card's Answer To Reset (not required)
        hresult, n, n, n, atr = SCardStatus(hcard)
        if hresult != SCARD_S_SUCCESS:
          raise Exception('Failed to get ATR: ' + SCardGetErrorMessage(hresult))
        print "ATR            :", smartcard.util.toHexString(atr)

      # Header and document data
      if not silent or report:
        # Start communication, send GET DATA header
        data = card_transmit(hcard, dwActiveProtocol, cmd['GET_DATA_0101'])
        data = smartcard.util.toHexString(data, smartcard.util.PACK)
        print "Header field   :", data
        print "Printed number :", " "*17, data[18:32]

        # Select EF path 0f 02
        data = eid_read_ef(hcard, dwActiveProtocol, files['DOCUMENT'], dump_directory)
        fdata, flabels = eid_data_split_fields(data)
        print "eID number     :", b2a(fdata[0])
        print "Issued         :", b2a(fdata[3])
        print "Valid          :", b2a(fdata[4])
        print "Issuer         :", b2u(fdata[5]), b2a(fdata[6])

      # Personal data
      read_personal = not silent or report
      # We still need jmbg from the personal details
      if (photo and not photo_filename) or (qualified and not qualified_filename) or (standard and not qualified_filename):
        read_personal = True

      if read_personal:
        # Select EF path 0f 03
        data = eid_read_ef(hcard, dwActiveProtocol, files['PERSONAL'], dump_directory)
        fdata, flabels = eid_data_split_fields(data)
        jmbg = b2a(fdata[0])
        if not silent:
          print "JMBG           :", jmbg
          print "Family name    :", b2u(fdata[1])
          print "First name     :", b2u(fdata[2])
          print "Middle name    :", b2u(fdata[3])
          print "Gender         :", b2u(fdata[4])
          # Community of birth is optional, ending is SRB, and before we have date of birth
          print "Place od birth :", ', '.join([b2u(t) for t in fdata[5:len(fdata)-2]])
          print "Date of birth  :", b2a(fdata[len(fdata)-2])


      # Place of residence data
      if not silent or report:
        # Select EF path 0f 04
        data = eid_read_ef(hcard, dwActiveProtocol, files['RESIDENCE'], dump_directory)
        fdata, flabels = eid_data_split_fields(data)

        residence  = "%s, %s, %s" % (b2u(fdata[1]), b2u(fdata[2]), b2u(fdata[0]))
        if len(fdata) > 3:
          residence = string.join([b2u(d) for d in fdata[3:]], ', ')+"\n"+" "*17+residence
        print "Residence      :", residence


      # Dump files without extracting and saving individual files
      if dump_directory:
        for n in (files['PHOTO'], files['QUALIFIED'], files['STANDARD']):
          eid_read_ef(hcard, dwActiveProtocol, n, dump_directory)

      # Do not trust the JMBG
      jmbg = os.path.basename(jmbg)

      if photo:
        # Select EF path 0f 06
        data = eid_read_ef(hcard, dwActiveProtocol, files['PHOTO'], None)
        if not photo_filename: filename = jmbg+".jpg"
        else: filename = photo_filename
        eid_data_extract_file(data, filename)

      if qualified:
        # Select EF path 0f 08
        data = eid_read_ef(hcard, dwActiveProtocol, files['QUALIFIED'], None)
        if not data:
          print >> sys.stderr, "Missing qualified certificate"
        else:
          if not qualified_filename: filename = jmbg+"_qualified.cer"
          else: filename = qualified_filename
          eid_data_extract_file(data, filename)

      if standard:
        # Select EF path 0f 10
        data = eid_read_ef(hcard, dwActiveProtocol, files['STANDARD'], None)
        if not data:
          print >> sys.stderr, "Missing standard certificate"
        else:
          if not standard_filename: filename = jmbg+"_standard.cer"
          else: filename = standard_filename
          eid_data_extract_file(data, filename)

    finally:
      card_disconnect(hcard)

  finally:
    release_context(hcontext)

#  except Exception, message:
#    print >> sys.stderr, "Error:", message
#    raise message

if __name__ == "__main__":
  main()

