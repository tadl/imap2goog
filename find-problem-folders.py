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
    # stuff all source folder names into list
    folderlist.append(name)
    if (count == 4962):
        print "Source folder has max messages (4962): %s" % name

folderlist_transformed = []
for fn in folderlist:
    new_fn = re.sub(r'^Cabinet/','',fn)
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


