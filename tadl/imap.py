import re
from imaplib import ParseFlags

def parseFolder(folder_data):
    m = re.search('^(\(.*\)) "(.*)" "(.*)"', folder_data)
    return m.group(1), m.group(2), m.group(3)

def getAllFolders(imap_connection):
    i = imap_connection
    folder_data = []
    stat, list = i.list()
    if (stat != "OK"):
        raise Exception('list failed')
    for folder in list:
        flags, root, name = parseFolder(folder)
        folder_tuple = (flags, root, name)
        folder_data.append(folder_tuple)
    # 'Work In Progress' is excluded from LIST output. We add it here.
    folder_data.append((r'(\Noinferiors \Unmarked)', '/', 'Work In Progress'))
    return folder_data

def getMessageCount(imap_connection, folder_name):
    i = imap_connection
    folder = folder_name
    stat, data = i.select(folder, 1)
    if (stat != "OK"):
        raise Exception('select failed')
    count = int(data[0])
    return count

def getFlags(imap_connection):
    i = imap_connection
    flag_data = []
    status, data = i.uid("fetch", "1:*", "(FLAGS)")
    if (data == [None]):
        return []
    for record in data:
        #print "record: %s" % record
        m = re.match("^(\d+) \(FLAGS \(.*\) UID (.*)\)$", record)
        num = m.group(1)
        uid = m.group(2)
        flags = ParseFlags(record)
        flag_tuple = (uid, flags)
        flag_data.append(flag_tuple)
        #print "message %s has uid %s, flags %s" % (num, uid, flags)
    return flag_data

import csv

def getCredentials(username, filename):
    f = file(filename, 'r')
    r = csv.DictReader(f)
    for dict in r:
        if (dict['user'] == username):
            return dict['password']

def is_inbox_folder(foldername):
    if (foldername == "INBOX"):
        return True

    if (re.search(r'^(Cabinet/)?gw_INBOX', foldername)):
        return True

    return False

def is_sent_folder(foldername):
    if (foldername == "Sent Items"):
        return True

    if (re.search(r'^Sent Items\.dup.*', foldername)):
        return True

    if (re.search(r'^Sent Items_OLD.*', foldername)):
        return True

    return False

