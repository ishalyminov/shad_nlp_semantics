#!/usr/bin/python
################################################################################

import sys
import cmd
import sqlite3
import traceback

import earley
import logic_to_sql

def filter_comments(in_lines):
    return [line for line in in_lines if len(line.strip()) and not line.strip()[0] == '#']

class SimpleREPL(cmd.Cmd):
    def __init__(self, stream):
        print repr(stream)
        cmd.Cmd.__init__(self, "Tab", stream)
        self.prompt = ">> "
        self.intro = """
Ask on some of your favourite food.
There are a few service commands:

  .init     Creates all tables
  .fini     Drops all tables
  .dump     Dumps all tables
  .debug    Enables/disables NLP debugging
  .trace    Enables/disables SQL tracing
"""
        self.interactive = (stream == sys.stdin)
        self.connection = sqlite3.connect("example.db")
        self.grammar = earley.load_grammar(filter_comments(open("repl.txt", "r").readlines()))
        self.debug = True
        self.trace = True

        if not self.interactive:
            self.use_rawinput = False

    def _execute(self, query):
        if self.trace:
            print "<", query

        cursor = self.connection.cursor()
        for row in cursor.execute(query):
            yield row
        cursor.close()

        self.connection.commit()

    def _execute_sync(self, query):
        for row in self._execute(query):
            pass

    def cmd_init(self):
        self._execute_sync("CREATE TABLE my_consists(arg0 TEXT, arg1 TEXT)")
        self._execute_sync("CREATE TABLE my_is(arg0 TEXT, arg1 TEXT)")
        # self._execute_sync("CREATE TABLE my_hates(arg0 TEXT, arg1 TEXT)")

    def cmd_fini(self):
        self._execute_sync("DROP TABLE my_consists")
        self._execute_sync("DROP TABLE my_is")
        # self._execute_sync("DROP TABLE my_hates")

    def cmd_clear(self):
        self._execute_sync("DELETE FROM my_consists")
        self._execute_sync("DELETE FROM my_is")
        # self._execute_sync("DELETE FROM my_hates")

    def cmd_debug(self):
        if self.debug:
            self.debug = False
            print "NLP debugging disabled."
        else:
            self.debug = True
            print "NLP debugging enabled."

    def cmd_trace(self):
        if self.trace:
            self.trace = False
            print "SQL tracing disabled."
        else:
            self.trace = True
            print "SQL tracing enabled."

    def cmd_dump(self):
        print "== Contains =" + "=" * 70
        for row in self._execute("SELECT * FROM my_consists"):
            print ":", "Consists(%s)" % ", ".join(row)
        
        '''print "== Hates =" + "=" * 70
        for row in self._execute("SELECT * FROM my_hates"):
            print ":", "Hates(%s)" % ", ".join(row)'''

    def cmd_eval(self, semantics):
        for query in logic_to_sql.SqlGenerator().make_sql(semantics):
            for row in self._execute(query):
                print ":", " ".join([str(element) for element in row])

    def emptyline(self):
        pass

    def default(self, string):
        try:
            if not self.interactive:
                print string
            if string == ".init":
                self.cmd_init()
            elif string == ".fini":
                self.cmd_fini()
            elif string == ".clear":
                self.cmd_clear()
            elif string == ".debug":
                self.cmd_debug()
            elif string == ".trace":
                self.cmd_trace()
            elif string == ".dump":
                self.cmd_dump()
            elif string == "what is the meaning of life":
                print "42."
            else:
                variants = earley.parse(self.grammar, string)

                if len(variants) == 0:
                    print '(!) Unable to parse query.'
                elif len(variants) > 1:
                    print '(!) Query is ambiguous.'
                    for semantics, tree in variants:
                        print "    ", earley.qtree(tree)
                else:
                    semantics, tree = variants[0]
                    if self.debug:
                        print
                        print "T=", string
                        print "Q=", earley.qtree(tree)
                        print "S=", semantics
                        print "S=", semantics.simplify()
                        print
                    self.cmd_eval(semantics.simplify())
            print
            print "Okay."
            print
        except RuntimeError as e:
            traceback.print_exc()

    def do_EOF(self, line):
        print 
        print "Ciao!"
        return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        stream = open(sys.argv[1], "r")
    else:
        stream = sys.stdin

    SimpleREPL(stream).cmdloop()
