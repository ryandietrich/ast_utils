#!/usr/bin/env python

"""
This program will look for any class that inherits from a class.

Examples:

Find all the classes that inherit from model_base.BASEV2 in the neutron directory.

./inherits_from.py /opt/stack/neutron/neutron model_base.BASEV2

./inherits_from.py /opt/stack/cinder/cinder rpc.RPCAPI
"""

import fnmatch
import json
import os
import sys

from pprint import pprint

import ast_parser

def merge_two_dicts(x, y):
    '''Given two dicts, merge them into a new dict as a shallow copy.'''
    z = x.copy()
    z.update(y)
    return z

def traverseMatches(matches, filesFound, toCheck):
    ''' Iterate over the file/directory matches, and see if they inherit from our toCheck list '''
    outbound = {}
    for mtch in matches:
        if "/tests/" in mtch:
            continue

        res = ast_parser.parseFile(mtch)
        for filename in res.keys():
            for clz in res[filename]['classes']:
                inheritsFrom = res[filename]['classes'][clz]['inheritsFrom']
                if len(inheritsFrom) > 0:
                    for val in inheritsFrom:
                        baseName = ".".join(val)
                        if baseName in toCheck:
                            #print "filename=%s, class=%s, inheritsFrom=%s" % ( filename, clz, str(inheritsFrom) )
                            outbound[clz] = filename
                            filesFound.append(filename)
    return outbound

def handle(targetDir, toCheck):
    ''' Walk the targetDir, and call traverseMatches until everything that inherits from toCheck, or from the modules that inherit from toCheck are resolved '''
    matches = []
    filesFound = []
    classesFound = {}

    for root, dirnames, filenames in os.walk(targetDir):
        for filename in fnmatch.filter(filenames, '*.py'):
            matches.append(os.path.join(root, filename))

    prevCount = len(filesFound)

    while True:
        toCheck      = traverseMatches(matches, filesFound, toCheck)
        classesFound = merge_two_dicts(classesFound, toCheck)
        toCheck      = toCheck.keys()

        if prevCount == len(filesFound):
            break
        prevCount = len(filesFound)

    return classesFound

if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise Exception("usage: inherits_from.py DIR CLASS...")

    targetDir = sys.argv[1]
    toCheck   = sys.argv[2:]

    #print "targetDir = %s, toCheck = %s" % ( targetDir, str(toCheck) )

    result = handle(targetDir, toCheck)
    print json.dumps(result, indent=4, sort_keys=True)
    #pprint(result)
