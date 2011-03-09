#!/usr/bin/python

from imaplib import IMAP4, ParseFlags
import re
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

folderlist = []

for folder in folders:
    flags, root, name = folder
    count = getMessageCount(imap, name)
    if (verbose):
        print 'Folder "%s" has %s messages.' % (name, count)
        if (is_inbox_folder(name)):
            print 'Folder "%s" is an inbox-equivalent.' % name
        if (is_sent_folder(name)):
            print 'Folder "%s" is a sent-items-equivalent.' % name
    # stuff all source folder names into list
    folderlist.append(name)
    if (count == 4962):
        print "Source folder has max messages (4962): %s" % name

folderlist_transformed = []
for fn in folderlist:
    new_fn = re.sub(r'^Cabinet/','',fn)
    new_fn = re.sub(r'_overflow.$', '', new_fn)
    folderlist_transformed.append(new_fn)
    if (verbose):
        print "Folder %s => %s" % (fn, new_fn)

fn_dict = {}
# count each folder name after transformation
for folder in folderlist_transformed:
    try:
        fn_dict[folder] += 1
    except:
        fn_dict[folder] = 1

for key in fn_dict.keys():
    # warn about any collisions (where the transformed name matched an existing)
    if (fn_dict[key] > 1):
        print "Potential collision with folder name %s" % key
    # warn about folders whose name is longer than a gmail label's limit
    if (len(key) > 40):
        print "Transformed folder name is >40 chars: %s" % key

special_folders = ['INBOX','Sent Items','Junk Mail','Trash','Work In Progress',
 'Calendar', 'Cabinet','Checklist']
special_dict = {}
for special in special_folders:
    special_dict[special] = False

for folder in folderlist:
    for special in special_folders:
        re_string = '^' + special + '$'
        match = re.search(re_string,folder)
        if (match):
            if (verbose):
                print 'Found special folder %s' % folder
            # This SELECT test is somewhat pointless, because we should have
            # failed with an exception earlier in getMessageCount()
            try:
                (stat, data) = imap.select(folder)
            except:
                if (verbose):
                    print 'Exception while selecting %s' % folder
            if (stat == 'OK'):
                special_dict[special] = True
            else:
                print 'Found, but unable to select special folder %s' % folder

for special in special_dict.keys():
    if (special_dict[special] == False):
        print 'DID NOT find special folder %s' % special

optional_specials = ['Sent Items.dup1']

for folder in folderlist:
    for special in optional_specials:
        re_string = '^' + special + '$'
        match = re.search(re_string,folder)
        if (match):
            print "Found OPTIONAL special folder %s" % folder

