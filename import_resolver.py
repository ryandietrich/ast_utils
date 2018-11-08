#!/usr/bin/env python

"""
This program is responsible for iterating over all the files and subdirectories of TARGET_DIR, and figuring out all the locations on disk of each import made in that file.
Additionally, if that file is an "__init__", and there happens to be an "API" function.  We will instantiate that function, and figure out what class was loaded on the init's behalf (of the configuration).
"""

import copy
import fnmatch
import imp
import inspect
import json
import os
import pkgutil

import sys
import traceback
import types
from pprint import pprint

# Perl's Findbin, sort of :/
bindir = os.path.abspath(os.path.dirname(__file__))
sys.path.append("%s/../lib" % bindir)

import ast_parser

def getFilenameByImport(modulepath, filename):
    try:
        res = __import__(modulePath)
        return inspect.getfile(res)
    except Exception as ex:
        return None

def figureOutFilenameForModule(modulePath, filename):
    path = modulePath.split('.')
    backupPath  = copy.deepcopy(path)

    try:
        res = pkgutil.get_loader(modulePath)
        #print "Past loader for %s" % modulePath
        if res is not None and hasattr(res, "filename"):
            return { "filepath" : res.get_filename() }
    except Exception as ex:
        res = getFilenameByImport(modulePath, filename)

    pos = -1
    while abs(pos) != len(path):
        try:
            res = pkgutil.get_loader(".".join(path[:pos]))
            if res is not None and hasattr(res, "filename"):
                return { "filepath" : res.get_filename() }
        except Exception as ex:
            pass
        pos = pos - 1

    return None

def main():
    couldNotFind = {}
    errors = {}
    success = {}
    filesToProcess = []

    targetFile = sys.argv[1]
    filesToProcess.append(targetFile)

    for fname in filesToProcess:
        parsed = ast_parser.parseFile(fname)

        # Iterate over each filename in the response from the ast parser
        for filename in parsed.keys():
            success[filename] = {}

            # Iterate over each class imported by the current file
            for clz in parsed[filename]['imports'].keys():
                for asName, modulePath in parsed[filename]['imports'][clz].iteritems():
                    res = None
                    try:
                        res = figureOutFilenameForModule(modulePath, filename)
                        #print "filename=%s, res=%s" % ( filename, res )
                    except Exception as ex:
                        print "modulePath=%s, filename=%s" % ( str(modulePath), filename )
                        traceback.print_exc()
                        if filename not in errors.keys():
                            errors[filename] = []
                        errors[filename].append(modulePath)

                    # Either write the success to disk, or write it to the list of modules we could not figure out the path for
                    success[filename][modulePath] = res
                    if res is None:
                        if filename not in couldNotFind.keys():
                            couldNotFind[filename] = []
                        couldNotFind[filename].append(modulePath)

    myOutbound = { "couldNotFind" : couldNotFind, "errors" : errors, "success" : success }
    print json.dumps(myOutbound, indent=4, sort_keys=True)

if __name__ == '__main__':
    main()
