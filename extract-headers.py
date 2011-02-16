#!/usr/bin/python

from imaplib import IMAP4, ParseFlags
import re
import email
from tadl.imap import *

from optparse import OptionParser
op = OptionParser()
op.add_option("-u", "--user", dest="user")
op.add_option("-v", "--verbose", action="store_true", dest="verbose")
(options, args) = op.parse_args()
if (options.user == None):
    op.error('-u/--user argument is required')

verbose = False
if (options.verbose):
    verbose = True

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

for folder in folders:
    flags, root, name = folder
    count = getMessageCount(imap, name)
    messageflags = getFlags(imap)
    for (uid, flags) in messageflags:
        stat, data = imap.uid("fetch", uid, "(BODY.PEEK[HEADER])")
        if (stat != "OK"):
            print "Fetch failed for uid %s" % uid
        else:
            msgstr = data[0][1]
            msg = email.message_from_string(msgstr)
            hdr_to = msg.get("To")
            hdr_from = msg.get("From")
            hdr_cc = msg.get("Cc")
            print "TO %s" % hdr_to
            print "FROM %s" % hdr_from
            print "CC %s" % hdr_cc
