#!/usr/bin/env python

from imaplib import IMAP4
import email
import re
from cStringIO import StringIO
from email.generator import Generator

from tadl.imap import *

import ConfigParser
config = ConfigParser.ConfigParser()
config.read('migration.cfg')
imap_server = config.get('IMAP', 'server')

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

imap_user = options.user
imap_password = getCredentials(imap_user, 'credentials.csv')

imap = IMAP4(imap_server)
imap.login(imap_user, imap_password)
imap.debug = 2

cal_count = getMessageCount(imap, "Calendar")

print cal_count, "items in Calendar folder."

messageflags = getFlags(imap)

def msg2string(msg, unixfrom=False):
    fp = StringIO()
    g = Generator(fp, mangle_from_=False)
    g.flatten(msg, unixfrom=unixfrom)
    text = fp.getvalue()
    return text

def SaveMessage(message):
    mbox_filename = imap_user + '.mbox'
    mbox_target = open(mbox_filename, 'ab')
    mbox_target.write(msg2string(message, unixfrom=True))
    mbox_target.close()

vcalendar_filename = imap_user + '.vcalendar'
vcalendar_target = open(vcalendar_filename, 'wb')

vcalendar_target.write('BEGIN:VCALENDAR\n')
vcalendar_target.write('VERSION:2.0\n')

for (uid, flags) in messageflags:
    stat, data = imap.uid("fetch", uid, '(RFC822)')
    msgstr = data[0][1]
    msg = email.message_from_string(msgstr)
    SaveMessage(msg)
    part_iter = email.iterators.typed_subpart_iterator(msg, 'text', 'calendar')
    for part in part_iter:
        vcal = part.get_payload(decode=True)
        vcal = re.sub(r'\r\n', '\n', vcal)
        for line in vcal.splitlines():
            if re.search(r'^BEGIN:VCALENDAR', line):
                continue
            if re.search(r'^VERSION:', line):
                continue
            if re.search(r'^PRODID:', line):
                continue
            if re.search(r'^END:VCALENDAR', line):
                continue
            vcalendar_target.write(line + '\n')
vcalendar_target.write('END:VCALENDAR\n')
