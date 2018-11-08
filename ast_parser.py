#!/usr/bin/env python

"""
This is an AST based approach of finding all imports, instantiations, and function calls within a program.

A traditional "dump" from ast directly does not clearly depict the hierarchy of concepts, well.

This program has it's own problems, as it doesn't handle all of the possibilities that a programmer can do.
I wrote this to target parsing OpenStack to determine where database calls were made for every API call of every service (seriously).

usage: ./ast_parser [filename]

r.dietrich
8 November 2018
"""

import ast
import logging
import os
import sys
from pprint import pprint

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s : %(message)s" )

class Current(object):
    outbound = { "classes" : {}, "imports" : {} }
    currentFilename = ""
    currentFullPath = ""

    @staticmethod
    def reset():
        Current.outbound = { "classes" : {}, "imports" : {} }
        Current.currentFilename = ""

    @staticmethod
    def buildCurrent(name, inheritsFrom):
        Current.outbound["classes"][name] = {
            "functions" : {},
            "assignments" : [],
            "inheritsFrom" : inheritsFrom
        }
        Current.outbound["imports"][name] = {}

    @staticmethod
    def add(
        obj, currentClass, currentFunction, currentFilename,
        method, args, lineno, col_offset,
        target=None, value=None
    ):
        obj.append({
            "currentFunction" : currentFunction,
            "currentClass" : currentClass,
            "currentFilename" : currentFilename,
            "method" : method,
            "args" : args,
            "lineno" : lineno,
            "col_offset" : col_offset,
            "target" : target,
            "value" : value
        })

class ChildOfAttributeLister(ast.NodeVisitor):
    def visit_Attribute(self, node):
        logging.debug("(%d) Child of attribute!" % node.lineno)

        myAttr = None
        if hasattr(node, "attr"):
            logging.debug("    (%d) %s (ATTR)" % ( node.lineno, node.attr ))
            myAttr = node.attr
        elif hasattr(node, "id"):
            logging.debug("    (%d) %s (ID)" % ( node.lineno, node.id ))
            self.objectPath.append(node.id)

        self.generic_visit(node)

        if myAttr is not None:
            logging.debug("    %s - %d (ATTR)" % ( myAttr, node.lineno ))
            self.objectPath.append(node.attr)

    def visit_Call(self, node):
        #print dir(node)
        #print dir(node.func)
        #print dir(node.func.value)
        #print dir(node.func.value.value)
        #print node.func.value.value.id
        #print node.lineno
        #print node.col_offset
        #print "\n\n"

        if hasattr(node.func, "id"):
            method = node.func.id
        else:
            method = None # FIXME

        outbound = {
            "currentClass" : self.currentClass,
            "currentFunction" : self.currentFunction,
            "method" : method,
            "args" : [],
            "lineno" : node.lineno,
            "col_offset" : node.col_offset
        }
        for arg in node.args:
            cal = ChildOfAttributeLister()
            cal.objectPath = []
            cal.currentClass = self.currentClass
            cal.currentFunction = self.currentFunction
            cal.visit(arg)
            outbound["args"].append(cal.objectPath)

        self.objectPath.append(outbound)

    def visit_Name(self, node):
        logging.debug("(%d) Name of Child attribute: %s, class=%s, function=%s" % ( node.lineno, node.id, self.currentClass, self.currentFunction ))
        self.objectPath.append(node.id)

    def visit_Str(self, node):
        self.objectPath.append(node.s)
        logging.debug("(%d) Str of Child attribute: %s, class=%s, function=%s" % ( node.lineno, node.s, self.currentClass, self.currentFunction ))

class ChildOfCallLister(ast.NodeVisitor):
    def visit_Attribute(self, node):
        logging.debug("(%d) Child of call: type=%s" % ( node.lineno, type(node) ))

        ca = ChildOfAttributeLister()
        ca.currentClass = self.currentClass
        ca.currentFunction = self.currentFunction
        ca.objectPath = self.objectPath
        ca.visit(node)

class ChildOfFunctionLister(ast.NodeVisitor):
    # Arguments to current function we are parsing
    def visit_arguments(self, node):
        logging.debug("Child of function: type=%s" % ( type(node) ))
        for arg in node.args:
            self.myParams.append(arg.id)

    def visit_ImportFrom(self, node):
        for nm in node.names:
            if nm.asname is not None:
                Current.outbound["imports"][Current.currentFilename][nm.asname] = "%s.%s" % ( node.module, nm.name )
            else:
                Current.outbound["imports"][Current.currentFilename][nm.name] = "%s.%s" % ( node.module, nm.name )

    def visit_Import(self, node):
        for nm in node.names:
            #print "Import: %s as %s" % ( nm.name, nm.asname )
            if nm.asname is not None:
                Current.outbound["imports"][Current.currentFilename][nm.asname] = nm.name
            else:
                Current.outbound["imports"][Current.currentFilename][nm.name] = nm.name

    def visit_Call(self, node):
        argsToCall = []
        for arg in node.args:
            if isinstance(arg, ast.Call):
                if hasattr(arg, "func") and hasattr(arg.func, "attr"):
                    # If the function takes functions as arguments, then we gotta go handle that as well :(
                    # XXX refactor to re-use existing functions at some point :/
                    childOfCall = ChildOfCallLister()
                    childOfCall.objectPath = []
                    childOfCall.currentClass = self.currentClass
                    childOfCall.currentFunction = self.currentFunction
                    childOfCall.visit(arg.func)
                    #childOfCall.objectPath.reverse()

                    Current.add(
                        Current.outbound["classes"][self.currentClass]["functions"][self.currentFunction]["calls"],
                        self.currentClass, self.currentFunction, Current.currentFullPath,
                        childOfCall.objectPath, argsToCall, arg.func.lineno, arg.func.col_offset
                    )
            else:
                cal = ChildOfAttributeLister()
                cal.objectPath = []
                cal.currentClass = self.currentClass
                cal.currentFunction = self.currentFunction
                cal.visit(arg)
                #print cal.objectPath
                argsToCall.append(cal.objectPath)

        childOfCall = ChildOfCallLister()
        childOfCall.objectPath = []

        if hasattr(node, "func") and hasattr(node.func, "id"):
            childOfCall.objectPath.append(node.func.id)
            logging.debug("(%d) Function list func: %s" % ( node.lineno, node.func.id ))

        childOfCall.currentClass = self.currentClass
        childOfCall.currentFunction = self.currentFunction
        childOfCall.visit(node.func)

        #childOfCall.objectPath.reverse()

        Current.outbound["classes"][self.currentClass]["functions"][self.currentFunction]["arguments"] = self.myParams
        #seeIfMethodCallsSubordinateObjectNotImported(childOfCall.objectPath, Current.outbound["imports"][Current.currentFilename])

        Current.add(
            Current.outbound["classes"][self.currentClass]["functions"][self.currentFunction]["calls"],
            self.currentClass, self.currentFunction, Current.currentFullPath, childOfCall.objectPath,
            argsToCall, node.lineno, node.col_offset
        )

class CallForAssignLister(ast.NodeVisitor):
    def visit_Call(self, node):
        for arg in node.args:
            cal = ChildOfAttributeLister()
            cal.objectPath = []
            cal.currentClass = self.currentClass
            cal.currentFunction = self.currentFunction
            # XXX TODO REMOVE FOO
            #print arg
            #print dir(arg)
            #print arg.func.id
            #print dir(cal)
            cal.visit(arg)
            # elements in the argpath separated by dots are backwards (ie: compute_api.self vs. self.compute_api)
            #cal.objectPath.reverse()
            #print "helloooooo"
            #print cal.objectPath
            #self.argPath.append(".".join(cal.objectPath))
            self.argPath.append(cal.objectPath)

        childOfCall = ChildOfCallLister()
        childOfCall.objectPath = []

        if hasattr(node, "func") and hasattr(node.func, "id"):
            childOfCall.objectPath.append(node.func.id)

        childOfCall.currentClass = self.currentClass
        childOfCall.currentFunction = self.currentFunction
        childOfCall.visit(node.func)
        self.objectPath = childOfCall.objectPath

class AssignsForFunctionLister(ast.NodeVisitor):
    def visit_Assign(self, node):
        cal2 = ChildOfAttributeLister()
        cal2.currentClass = self.currentClass
        cal2.currentFunction = self.currentFunction
        cal2.objectPath = []
        cal2.visit(node.targets[0])

        if isinstance(node.value, ast.Call):
            # example foo = Thing.otherFunction()
            cal = CallForAssignLister()
            cal.currentClass = self.currentClass
            cal.currentFunction = self.currentFunction
            cal.argPath = []
            cal.objectPath = []
            cal.visit(node.value)

            Current.add(
                Current.outbound["classes"][self.currentClass]["functions"][self.currentFunction]["assignments"],
                self.currentClass, self.currentFunction, Current.currentFullPath,
                cal.objectPath, cal.argPath, node.lineno, node.col_offset, cal2.objectPath
            )

        elif isinstance(node.value, ast.Attribute):
            # example: foo = Thing.otherThing

            cal = ChildOfAttributeLister() # Get the right hand side
            cal.currentClass = self.currentClass
            cal.currentFunction = self.currentFunction
            cal.objectPath = []
            cal.visit(node.value)

            Current.add(
                Current.outbound["classes"][self.currentClass]["functions"][self.currentFunction]["assignments"],
                self.currentClass, self.currentFunction, Current.currentFullPath,
                cal.objectPath, node.lineno, node.col_offset, cal2.objectPath
            )

        elif isinstance(node.value, ast.Str):

            Current.add(
                Current.outbound["classes"][self.currentClass]["functions"][self.currentFunction]["assignments"],
                self.currentClass, self.currentFunction, Current.currentFullPath,
                node.value.s, node.lineno, node.col_offset, cal2.objectPath
            )

class FuncLister(ast.NodeVisitor):
    """
        This class extends NodeVisitor and handles imports, class definitions and functions.

        >>> Current.reset()
        >>> Current.currentFilename = "moocow"
        >>> Current.buildCurrent("moocow", [])
        >>> tree = ast.parse("abc = 'def'")
        >>> FuncLister().visit(tree)
        >>> Current.outbound is not None
        True
        >>> 'moocow' in Current.outbound['classes']
        True
        >>> 'abc' in Current.outbound['classes']['moocow']['assignments'][0]['target']
        True
        >>> 'def' in Current.outbound['classes']['moocow']['assignments'][0]['value']
        True
        >>> Current.outbound['classes']['moocow']['assignments'][0]['lineno'] == 1
        True
        >>> Current.outbound['classes']['moocow']['assignments'][0]['col_offset'] == 0
        True
        >>> len(Current.outbound['classes']['moocow']['functions'].keys())
        0
    """
    def visit_Import(self, node):
        #print "IMPORT !!!! %s - %s" % ( node.names[0].name, node.names[0].asname )
        for nm in node.names:
            #print "Import: %s as %s" % ( nm.name, nm.asname )
            if nm.asname is not None:
                Current.outbound["imports"][Current.currentFilename][nm.asname] = nm.name
            else:
                Current.outbound["imports"][Current.currentFilename][nm.name] = nm.name

    def visit_ImportFrom(self, node):
        #print "    from import - module %s - %s" % ( node.module, str(node.names) )
        for nm in node.names:
            if nm.asname is not None:
                Current.outbound["imports"][Current.currentFilename][nm.asname] = "%s.%s" % ( node.module, nm.name )
            else:
                Current.outbound["imports"][Current.currentFilename][nm.name] = "%s.%s" % ( node.module, nm.name )

            #print "From import: %s, %s as %s" % ( node.module, nm.name, nm.asname )

    def visit_ClassDef(self, node):
        self.currentClass = node.name

        inheritsFrom = []
        for base in node.bases:
            cal2 = ChildOfAttributeLister()
            cal2.currentClass = self.currentClass
            cal2.currentFunction = ""
            cal2.objectPath = []
            cal2.visit(base)
            #cal2.objectPath.reverse()
            inheritsFrom.append(cal2.objectPath)

        Current.buildCurrent(self.currentClass, inheritsFrom)
        #self.generic_visit(node)
        for item in node.body:
            self.visit(item)
        self.currentClass = Current.currentFilename

    def visit_FunctionDef(self, node):
        myCurrentClass = Current.currentFilename
        if hasattr(self, "currentClass"):
            myCurrentClass = self.currentClass

        Current.outbound["classes"][myCurrentClass]["functions"][node.name] = {
            "calls" : [],
            "lineno" : node.lineno,
            "assignments" : [],
            "currentClass" : myCurrentClass,
            "currentFilename" : Current.currentFullPath,
        }

        il = ChildOfFunctionLister()
        il.currentFunction = node.name
        il.currentClass    = myCurrentClass
        il.myParams        = []
        il.visit(node)

        al = AssignsForFunctionLister()
        al.currentFunction = node.name
        al.currentClass = myCurrentClass
        al.visit(node)

    def visit_Assign(self, node):
        myCurrentClass = Current.currentFilename
        if hasattr(self, "currentClass"):
            myCurrentClass = self.currentClass

        # Get the full name of the "left hand side" name
        cal2 = ChildOfAttributeLister()
        cal2.currentClass = myCurrentClass
        cal2.currentFunction = ""
        cal2.objectPath = []
        cal2.visit(node.targets[0])
        # XXX not sure about this commented out line
        #cal2.objectPath.reverse()

        if isinstance(node.value, ast.Call):
            # example foo = Thing.otherFunction()

            cal = CallForAssignLister()
            cal.currentClass = myCurrentClass
            cal.currentFunction = ""
            cal.argPath = []
            cal.objectPath = []
            cal.visit(node.value)

            Current.add(
                Current.outbound["classes"][myCurrentClass]["assignments"],
                myCurrentClass, None, Current.currentFullPath, cal.objectPath,
                cal.argPath, node.lineno, node.col_offset, cal2.objectPath
            )

        elif isinstance(node.value, ast.Attribute):
            # example: foo = Thing.otherThing

            # Get the right hand side
            cal = ChildOfAttributeLister()
            cal.currentClass = myCurrentClass
            cal.currentFunction = ""
            cal.objectPath = []
            cal.visit(node.value)

            #print "  assign? : objectPath=%s" % ( cal.objectPath )
            Current.add(
                Current.outbound["classes"][myCurrentClass]["assignments"],
                myCurrentClass, None, Current.currentFullPath, cal.objectPath,
                node.lineno, node.col_offset, cal2.objectPath
            )

        elif isinstance(node.value, ast.Str):
            Current.add(
                Current.outbound["classes"][myCurrentClass]["assignments"],
                myCurrentClass, None, Current.currentFullPath, None, None,
                node.lineno, node.col_offset, cal2.objectPath, node.value.s
            )
        elif isinstance(node.value, ast.Dict) or isinstance(node.value, ast.List):
            try:
                value = eval(compile(ast.Expression(node.value), "<ast expression>", "eval"))
            except Exception as ex:
                logging.debug("(%d) Error evaluating expression!" % node.lineno)
                value = None

            Current.add(
                Current.outbound["classes"][myCurrentClass]["assignments"],
                myCurrentClass, None, Current.currentFullPath, None, None,
                node.lineno, node.col_offset, cal2.objectPath, value
            )

#def seeIfMethodCallsSubordinateObjectNotImported(methodPath, imports):
#    # This function will try to see if a sub-module is called off of an import.
#    # This is important because we will need to resolve the actual file that is subordinate to the imported class
#    if len(methodPath) == 0:
#        return
#
#    #print "methodPath = %s" % str(methodPath)
#    if methodPath[0] == 'self':
#        methodPath.pop(0)
#
#    pos = 1
#    while pos <= len(methodPath):
#        print methodPath
#        partialPath = ".".join(methodPath[0:pos]) # Example: "objects"
#        if partialPath in imports.keys():
#            if pos + 1 < len(methodPath):
#                unresolved = ".".join(methodPath[0:pos + 1]) # Example: "objects.BackupList"
#                computed = unresolved.replace(partialPath, imports[partialPath]) # Example: "cinder.objects.BackupList"
#                imports[unresolved] = computed
#        pos = pos + 1

def getBasenameFromFilename(filename):
    """ A simple function for getting the filename from a path.

        >>> getBasenameFromFilename("/abc/def/foo.py")
        'foo'
    """
    return os.path.basename(filename).split(".")[0]

def handleFile(filename, fileContent, toReturn):
    """ Given a file, it's content, and a return structure to modify in place,
        parse the AST of the content.

        >>> res = handleFile("abc", "a = 'abc'", {})
        >>> "abc" in res
        True
        >>> "classes" in res['abc']
        True
        >>> len(res['abc']['classes']['abc']['assignments']) == 1
        True
    """

    Current.reset()
    cf = getBasenameFromFilename(filename)
    Current.currentFilename = cf
    Current.currentFullPath = filename
    Current.buildCurrent(cf, [])
    tree = ast.parse(fileContent)
    #print ast.dump(tree, False)
    FuncLister().visit(tree)
    toReturn[filename] = Current.outbound
    return toReturn

def parseFiles(files):
    """ Parse the files passed in as arguments, generate an uber-structure by filename

        >>> res = parseFiles([ sys.argv[0] ])
        >>> './sunrise_parser.py' in res
        True
    """
    toReturn = {}
    for filename in files:
        fileContent = open(filename).read()
        handleFile(filename, fileContent, toReturn)

    return toReturn

def parseFile(filename):
    return parseFiles([filename])

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "At least one filename or directory required!"
        sys.exit(1)

    if sys.argv[1] == "test":
        import doctest
        doctest.testmod(verbose=True)
        sys.exit(0)

    if len(sys.argv) > 2 and sys.argv[2] == "debug":
        classToDebug = None
        if len(sys.argv) == 4:
            classToDebug = sys.argv[3]

        result = parseFiles([sys.argv[1]])
        for filename in result:
            for clz in result[filename]["classes"]:
                if clz == classToDebug:
                    print clz
                    pprint(result[filename]["classes"][clz])
                elif classToDebug is None:
                    print clz
        sys.exit(0)

    result = parseFiles(sys.argv[1:])
    pprint(result)
