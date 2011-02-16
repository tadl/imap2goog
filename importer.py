#!/usr/bin/env python

from imaplib import IMAP4, ParseFlags
import email
import re
from email.utils import parsedate
from cStringIO import StringIO
from email.generator import Generator

from tadl.imap import *

import ConfigParser
config = ConfigParser.ConfigParser()
config.read('migration.cfg')
ga_domain = config.get('Google', 'domain')
ga_user   = config.get('Google', 'user')
ga_pass   = config.get('Google', 'pass')
imap_server = config.get('IMAP', 'server')

from optparse import OptionParser
op = OptionParser()
op.add_option("-n", "--dry-run", action="store_true", dest="dry_run")
op.add_option("-u", "--user", dest="user")
op.add_option("-t", "--target-user", dest="target_user")
(options, args) = op.parse_args()
if (options.user == None):
    op.error('-u/--user argument is required')

dry_run = options.dry_run
target_user = options.target_user

imap_user = options.user
imap_password = getCredentials(imap_user, 'credentials.csv')

imap = IMAP4(imap_server)
imap.login(imap_user, imap_password)
imap.debug = 2

folders = getAllFolders(imap)

allcount = 0

from gdata.apps.migration.service import MigrationService
from gdata.apps.service import AppsForYourDomainException

m = MigrationService(domain=ga_domain)
m.ClientLogin(ga_user, ga_pass)

def msg2string(msg):
    fp = StringIO()
    g = Generator(fp, mangle_from_=False)
    g.flatten(msg)
    text = fp.getvalue()
    return text

import csv
pattern_file = file('address_cleanups.csv', 'r')
pattern_reader = csv.DictReader(f)
address_cleanups = []
sent_from_cleanups = []
for dict in pattern_reader:
    pattern = dict['pattern']
    repl = dict['repl']
    if (dict['type'] == 'all'):
        address_cleanups.append(dict)
    if (dict['type'] == 'sent_from'):
        sent_from_cleanups.append(dict)

def clean_gw_addresses(address):
    for c in address_cleanups:
        address = re.sub(c['pattern'], c['repl'], address)
    return address

def clean_gw_message(msg):
    if (msg.get('To') != None):
        msg.replace_header('To', clean_gw_addresses(msg.get('To')))
    if (msg.get('From') != None):
        msg.replace_header('From', clean_gw_addresses(msg.get('From')))
    if (msg.get('Cc') != None):
        msg.replace_header('Cc', clean_gw_addresses(msg.get('Cc')))
    return msg

#for testing a single source folder
#folders = [(None, None, 'ExceptionTest')]

for folder in folders:
    flags, root, foldername = folder
    if (foldername == 'Calendar'):
        print "Skipping folder %s" % foldername
        break
    count = getMessageCount(imap, foldername)
    allcount += count
    print "%s has %s messages" % (foldername, count)
    messageflags = getFlags(imap)
    for (uid, flags) in messageflags:
        import_flags = []
        import_labels= []

        if (foldername == "INBOX"):
            folderlabel= "gw_INBOX"
            #import_flags.append('IS_INBOX')
        else:
            folderlabel= foldername

        if (foldername in ["Work In Progress", "Sent Items", "Trash"]):
            folderlabel= None

        if (folderlabel!= None):
            import_labels.append(folderlabel)

        if (foldername == 'Sent Items'):
            import_flags.append('IS_SENT')

        if (foldername == 'Work In Progress' or '\Draft' in flags):
            import_flags.append('IS_DRAFT')

        if ('\Seen' not in flags):
            import_flags.append('IS_UNREAD')

        if ('\Flagged' in flags):
            import_flags.append('IS_STARRED')

        if (foldername == "Trash"):
            import_flags.append('IS_TRASH')

        #print flags
        #print import_flags
        #print import_labels
        stat, data = imap.uid("fetch", uid, '(RFC822)')
        msgstr = data[0][1]
        msg = email.message_from_string(msgstr)
        #print msg.get("To")
        #print msg.get("From")
        date_hdr = msg.get("Date")
        date_tuple = parsedate(date_hdr)
        #print date_tuple
        msg = clean_gw_message(msg)
        ## HACK for testing!
        #import_flags.append('IS_SENT')
        if ('IS_SENT' in import_flags):
            msg_from = msg.get('From')
            for dict in sent_from_cleanups:
                msg_from = re.sub(dict['pattern'], dict['repl'], msg_from)
            msg.replace_header('From', msg_from)
        if (dry_run):
            print "Dry run! Not actually importing message %s" % msg.get("Message-ID")
        else:
            try:
                #mailentry = m.ImportMail(target_user, msg.as_string(unixfrom=False), import_flags, import_labels)
                mailentry = m.ImportMail(target_user, msg2string(msg), import_flags, import_labels)
            except AppsForYourDomainException, E:
                print "Caught expected exception, continuing on!"
                print "Exception content was: %s" % E
                print msg.get("Message-ID")
                print msg2string(msg)
            

print "%s total messages" % allcount


