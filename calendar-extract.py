#!/usr/bin/env python

from imaplib import IMAP4
import email
import re
from cStringIO import StringIO
from email.generator import Generator
from datetime import date

from tadl.imap import *

import ConfigParser
config = ConfigParser.ConfigParser()
config.read('migration.cfg')
imap_server = config.get('IMAP', 'server')

from optparse import OptionParser
op = OptionParser()
op.add_option("-u", "--user", dest="user")
op.add_option("-v", "--verbose", action="store_true", dest="verbose")
op.add_option("--skip-earlier-than", dest="skip_earlier_than")
(options, args) = op.parse_args()
if (options.user == None):
    op.error('-u/--user argument is required')

verbose = False
if (options.verbose):
    verbose = True

skip_earlier_than_date = None

if (options.skip_earlier_than):
    (lim_year, lim_month, lim_day) = re.split('-', options.skip_earlier_than)
    skip_earlier_than_date = date(int(lim_year), int(lim_month), int(lim_day))

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
    mbox_filename = imap_user + '_Calendar.mbox'
    mbox_target = open(mbox_filename, 'ab')
    mbox_target.write(msg2string(message, unixfrom=True))
    mbox_target.close()

def getStartDate(vcal_string):
    # change line endings
    vcal_string = re.sub(r'\r\n', '\n', vcal_string)
    for line in vcal_string.splitlines():
        if re.search(r'^DTSTART:', line):
            #print 'FOUND start time line: ', line
            m1 = re.search(r'^DTSTART:(\d{8})', line)
            date_string = m1.group(1)
            #print 'EXTRACTED start date string: ', date_string
            m2 = re.search(r'(\d{4})(\d\d)(\d\d)', date_string)
            year = int(m2.group(1))
            month = int(m2.group(2))
            day = int(m2.group(3))
            #print day, month, year
            date_to_return = date(year, month, day)
            return date_to_return

vcalendar_filename = imap_user + '.vcalendar'
vcalendar_target = open(vcalendar_filename, 'wb')

# Begin the vcalendar object to contain our vevent objects
vcalendar_target.write('BEGIN:VCALENDAR\n')
vcalendar_target.write('VERSION:2.0\n')

def writeVcal(vcal_string):
    vcal = re.sub(r'\r\n', '\n', vcal_string)
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

for (uid, flags) in messageflags:
    stat, data = imap.uid("fetch", uid, '(RFC822)')
    msgstr = data[0][1]
    msg = email.message_from_string(msgstr)
    part_iter = email.iterators.typed_subpart_iterator(msg, 'text', 'calendar')
    for part in part_iter:
        vcal = part.get_payload(decode=True)
        event_date = getStartDate(vcal)
        if skip_earlier_than_date is not None and event_date < skip_earlier_than_date:
            if verbose: print 'skipping event with date %s < %s' % (event_date, skip_earlier_than_date)
        else:
            if verbose: print 'EXPORTING event with date', event_date
            SaveMessage(msg)
            writeVcal(vcal)

# End the vcalendar object
vcalendar_target.write('END:VCALENDAR\n')
