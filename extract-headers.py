#!/usr/bin/python

from imaplib import IMAP4, ParseFlags
import re
import email
from tadl.imap import *

from optparse import OptionParser
op = OptionParser()
op.add_option("-u", "--user", dest="user")
op.add_option("-v", "--verbose", action="store_true", dest="verbose")
op.add_option("-c", "--csv", action="store_true", dest="csv")
op.add_option("--noout", action="store_true", dest="noout")
(options, args) = op.parse_args()
if (options.user == None):
    op.error('-u/--user argument is required')

verbose = False
if (options.verbose):
    verbose = True

noout = False
if (options.noout):
    noout = True

output_csv = False
if (options.csv):
    output_csv = True

if (output_csv):
    import csv
    import sys
    headerWriter = csv.DictWriter(sys.stdout,
        ['FOLDER', 'ID', 'DATE', 'TO', 'FROM', 'CC'])

import ConfigParser
config = ConfigParser.ConfigParser()
config.read('migration.cfg')
imap_server = config.get('IMAP', 'server')

imap_user = options.user
imap_password = getCredentials(imap_user, 'credentials.csv')

imap = IMAP4(imap_server)
imap.login(imap_user, imap_password)
imap.debug = 2

folders = getAllFolders(imap)

def print_headers(hdr_dict):
    if noout: return
    if (output_csv):
        headerWriter.writerow(hdr_dict)
    else:
        for key in hdr_dict:
            if (hdr_dict[key] != None):
                print "%s %s" % (key, hdr_dict[key])

for folder in folders:
    flags, root, name = folder
    if verbose: print "Getting message count for folder %s" % name
    count = getMessageCount(imap, name)
    messageflags = getFlags(imap)
    for (uid, flags) in messageflags:
        if verbose: print "Fetching message UID %s with flags %s in folder %s" % (uid, flags, name)
        stat, data = imap.uid("fetch", uid, "(BODY.PEEK[HEADER])")
        if (stat != "OK"):
            print "Fetch failed for uid %s" % uid
        else:
            msgstr = data[0][1]
            msg = email.message_from_string(msgstr)
            hdr_id = msg.get("Message-ID")
            hdr_date = msg.get("Date")
            hdr_to = msg.get("To")
            hdr_from = msg.get("From")
            hdr_cc = msg.get("Cc")
            hdr_dict = {'FOLDER': name, 'ID': hdr_id, 'DATE': hdr_date,
                        'TO': hdr_to, 'FROM': hdr_from, 'CC': hdr_cc}
            print_headers(hdr_dict)
