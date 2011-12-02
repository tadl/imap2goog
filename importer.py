#!/usr/bin/env python

from imaplib import IMAP4, ParseFlags
import email
import re
import time
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
op.add_option("-v", "--verbose", action="store_true", dest="verbose")
(options, args) = op.parse_args()
if (options.user == None):
    op.error('-u/--user argument is required')

if (options.target_user == None):
    op.error('-t/--target-user argument is required')

verbose = False
if (options.verbose):
    verbose = True

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

def msg2string(msg, unixfrom=False):
    fp = StringIO()
    g = Generator(fp, mangle_from_=False)
    g.flatten(msg, unixfrom=unixfrom)
    text = fp.getvalue()
    return text

import csv
pattern_file = file('address_cleanups.csv', 'r')
pattern_reader = csv.DictReader(pattern_file)
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

def determine_labels(folder):
    return_labels = []

    #Strip prefix Cabinet/ if it appears
    folder = re.sub(r'^Cabinet/','',folder)

    #Strip suffix _overflow.$ if it appears
    folder = re.sub(r'_overflow.$', '', folder)

    # We set a special label for items found in the inbox
    # This serves to prevent migration from "un-archiving"
    # messages that were delivered and archived during the dual-delivery pilot
    if (is_inbox_folder(folder)):
        label = "gw_INBOX"
    else:
        label = folder

    # These folders receive no labels
    if (folder in ["Work In Progress", "Trash"] or is_sent_folder(folder)):
        label = None

    if (label != None):
        return_labels.append(label)

    return return_labels

def determine_flags(folder, msg, imap_flags):
    return_flags = []

    if (is_sent_folder(folder)):
        return_flags.append('IS_SENT')

    if (folder == 'Work In Progress' or r'\Draft' in imap_flags):
        return_flags.append('IS_DRAFT')

    if (r'\Flagged' in imap_flags):
        return_flags.append('IS_STARRED')

    if (folder == "Trash"):
        return_flags.append('IS_TRASH')

    if (folder == "Junk Mail"):
        return_flags.append('IS_TRASH')

    if (folder == "pilot_dual_delivery"):
        return_flags.append('IS_INBOX')

    if (r'\Seen' not in imap_flags):
        #XXX: add if dual_delivery_end_date and message is before that
        date_hdr = msg.get("Date")
        date_tuple = parsedate(date_hdr)
        return_flags.append('IS_UNREAD')

    return return_flags

def ImportMessage(target_user, msg, import_flags, import_labels):
    tries=10
    tried=0
    delay=1
    max_delay = 60
    while (tries > 0):
        try:
            mailentry = m.ImportMail(target_user, msg2string(msg), import_flags, import_labels)
        except AppsForYourDomainException, E:
            argdict = E.args[0]
            if (argdict['status'] == 400):
                raise E
            else:
                if (argdict['status'] != 503):
                    print "Caught exception on %s and re-trying: %s" % (msg.get("Message-ID"), E)
        else:
            return mailentry
        tries -= 1
        tried += 1
        print "Sleeping for %s seconds" % delay
        time.sleep(delay)
        if (delay < max_delay):
            delay *= 2
    raise Exception('Unsuccessful after %s retries' % tried)

def SaveFailedMessage(message_to_save):
    mbox_filename = imap_user + '.mbox'
    _saveMessage(message_to_save, mbox_filename)

def SaveSkippedMessage(message_to_save):
    mbox_filename = imap_user + '_skipped.mbox'
    _saveMessage(message_to_save, mbox_filename)

def _saveMessage(message_to_save, mbox_filename):
    mbox_target = open(mbox_filename, 'ab')
    mbox_target.write(msg2string(message_to_save, unixfrom=True))
    mbox_target.write('\n')
    mbox_target.close()

#for testing a single source folder
#folders = [(None, None, 'ExceptionTest')]

for folder in folders:
    flags, root, foldername = folder
    if (foldername in ['Calendar', 'Do Not Import']):
        print "Skipping folder %s" % foldername
        continue
    count = getMessageCount(imap, foldername)
    allcount += count
    print "%s has %s messages" % (foldername, count)
    messageflags = getFlags(imap)
    for (uid, flags) in messageflags:
        import_flags = []
        import_labels= []

        #fetch and parse message
        stat, data = imap.uid("fetch", uid, '(RFC822)')
        msgstr = data[0][1]
        msg = email.message_from_string(msgstr)

        import_flags = determine_flags(foldername, msg, flags)
        import_labels = determine_labels(foldername)

        msg = clean_gw_message(msg)
        if ('IS_SENT' in import_flags):
            msg_from = msg.get('From')
            for dict in sent_from_cleanups:
                msg_from = re.sub(dict['pattern'], dict['repl'], msg_from)
            msg.replace_header('From', msg_from)
        if (dry_run):
            print "Dry run! Not actually importing message %s" % msg.get("Message-ID")
        else:
            if (verbose):
                print "importing message %s" % msg.get("Message-ID")
            try:
                #mailentry = m.ImportMail(target_user, msg.as_string(unixfrom=False), import_flags, import_labels)
                #mailentry = m.ImportMail(target_user, msg2string(msg), import_flags, import_labels)
                mailentry = ImportMessage(target_user, msg, import_flags, import_labels)
            except Exception, E:
                print "FAILED: Message %s exception %s" % (msg.get("Message-ID"), E)
                SaveFailedMessage(msg)

print "%s total messages" % allcount
