#!/usr/bin/python
################################################################################
# GLOSSARY
################################################################################
#   * Term
# Either terminal or non-terminal symbol.
#   * Production
# A right-hand side of a production rule; formally, a sequence of terms.
#   * Rule
# A set of all possible production rules, grouped by left-hand side.
#
# For example, in grammar:
#   S  -> NP VP
#   NP -> D N
#   NP -> John
#   D  -> the
#   D  -> a
#   N  -> cat
#   N  -> dog
#   ...
#
# "S", "NP", "VP", "D", "N", "John", "the", "a", "cat", "god"
#   are terms.
# [ "NP, "VP" ], [ "D", "N" ], [ "John" ], [ "the" ], [ "a" ], ...
#   are productions for productions rules (1) and (2) respectivelly.
# ("S", [ [ "NP" "VP" ] ]), ("NP", [ [ "D", "N" ], [ "John"] ]), ...
#   are rules.

import re
import itertools
import operator

import logic
import logic_ast_nodes

class Production(object):
    def __init__(self, semantics, *terms, **kwargs):
        self.semantics = semantics # This is a semantic expression for the production.
        self.terms = terms # This is a list of terms with corresponding semantic variables.
        self.safe_bindings = kwargs["safe_bindings"] if "safe_bindings" in kwargs else True

    def __len__(self):
        return len(self.terms)

    def __getitem__(self, index):
        return self.terms[index][0]

    def __iter__(self):
        return itertools.imap(operator.itemgetter(0), self.terms)

    def __repr__(self):
        return \
            ("(:" + str(self.semantics) + ") " if self.semantics else "") + \
            " ".join(str(t) + (":" + str(s) if s else "") for t, s in self.terms)

    def __eq__(self, other):
        if not isinstance(other, Production):
            return False
        return \
            (self.semantics,  self.terms) == \
            (other.semantics, other.terms)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self.semantics, self.terms))

    def get_semantics(self, terms_semantics):
        assert(len(self.terms) == len(terms_semantics))

        bindings = dict(zip(map(operator.itemgetter(1), self.terms), terms_semantics))
        return self.semantics.replace_with_bindings(bindings, self.safe_bindings)

class Rule(object):
    def __init__(self, name, *productions):
        self.name = name
        self.productions = list(productions)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "%s -> %s" % (
            self.name,
            " | ".join(repr(p) for p in self.productions))

    def add(self, *productions):
        self.productions.extend(productions)

# State is a 3-tuple of a dotted rule, start column and end column.
# State also stores semantic expressions for every non-terminal in the right-hand side.
class State(object):
    # A dotted rule is represented as a (name, production, dot_index) 3-tuple.
    def __init__(self, name, production, semantics, dot_index, start_column, end_column = None):
        self.name = name
        self.production = production
        self.semantics = semantics
        self.dot_index = dot_index

        self.start_column = start_column
        self.end_column = end_column
        
        self.rules = [ term for term in self.production if isinstance(term, Rule) ]

    def __repr__(self):
        terms = map(str, self.production)
        terms.insert(self.dot_index, "$")

        return "%-5s -> %-23s [%2s-%-2s]" % (
            self.name,
            " ".join(terms),
            self.start_column,
            self.end_column)

    def __eq__(self, other):
        if not isinstance(other, State):
            return False
        return \
            (self.name,  self.production,  self.semantics,  self.dot_index,  self.start_column) == \
            (other.name, other.production, other.semantics, other.dot_index, other.start_column)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self.name, self.production))

    def is_completed(self):
        return self.dot_index >= len(self.production)

    def get_next_term(self):
        if self.is_completed():
            return None
        return self.production[self.dot_index]

    def get_semantics(self):
        return self.production.get_semantics(self.semantics)

# Column is a list of states in a chart table.
class Column(object):
    def __init__(self, index, token):
        self.index = index
        self.token = token

        self.states = []
        self._predecessors = {}

    def __str__(self):
        return str(self.index)

    def __len__(self):
        return len(self.states)

    def __iter__(self):
        return iter(self.states)

    def __getitem__(self, index):
        return self.states[index]

    def add(self, state, predecessor = None):
        if state not in self._predecessors:
            self._predecessors[state] = set()
            state.end_column = self
            self.states.append(state)
        if predecessor is not None:
            self._predecessors[state].add(predecessor)

    def dump(self, only_completed = False):
        print " [%s] %r" % (self.index, self.token)
        print "=" * 40
        for s in self.states:
            if only_completed and not s.is_completed():
                continue
            print repr(s)
        print "=" * 40
        print
    
    def predecessors(self, state):
        return self._predecessors[state]

class Node(object):
    def __init__(self, value, children):
        self.value = value
        self.children = children

    def dump(self, level = 0):
        print "  " * level + str(self.value)
        for child in self.children:
            child.dump(level + 1)

# INTERNAL SUBROUTINES FOR EARLEY ALGORITHM
################################################################################

def predict(column, rule):
    for production in rule.productions:
        column.add(
            State(
                rule.name,
                production,
                [],
                0,
                column))

def scan(column, state, token):
    if token != column.token:
        return
    column.add(
        State(
            state.name,
            state.production,
            state.semantics + [ None ],
            state.dot_index + 1,
            state.start_column), (state, None))

def complete(column, state):
    if not state.is_completed():
        return
    for prev_state in state.start_column:
        term = prev_state.get_next_term()
        if not isinstance(term, Rule):
            continue
        if term.name == state.name:
            column.add(
                State(
                    prev_state.name,
                    prev_state.production,
                    prev_state.semantics + [ state.get_semantics() ],
                    prev_state.dot_index + 1,
                    prev_state.start_column), (prev_state, state))

GAMMA_RULE = "GAMMA"

# ENTRY POINT FOR EARLEY ALGORITHM
################################################################################
def parse(starting_rule, text):
    text_with_indexes = enumerate([ None ] + text.lower().split())

    table = [ Column(i, token) for i, token in text_with_indexes ]
    table[0].add(State(
        GAMMA_RULE,
        Production(logic.parse_logic_expression("S"), (starting_rule, "S")),
        [],
        0,
        table[0]))

    for i, column in enumerate(table):
        for state in column:
            if state.is_completed():
                complete(column, state)
            else:
                term = state.get_next_term()
                if isinstance(term, Rule):
                    predict(column, term)
                elif i + 1 < len(table):
                    scan(table[i + 1], state, term)
        
        # XXX(sandello): You can uncomment this line to see full dump of
        # the chart table.
        #
        # column.dump(only_completed = False)

    # Find Gamma rule in the last table column or fail otherwise.
    result = []
    for state in table[-1]:
        if state.name == GAMMA_RULE and state.is_completed():
            result.extend(
                (state.get_semantics(), tree) for tree in build_trees(state, table))
    return result

# AUXILIARY ROUTINES
################################################################################
def build_trees(state, table):
    for children in build_children(state, table, []):
        yield Node(state, [c for c in reversed(children)])

def build_children(state, table, prev_children):
    has_predecessor = False
    for predecessor, child in table[state.end_column.index].predecessors(state):
        has_predecessor = True
        if child is not None:
            for tree in build_trees(child, table):
                prev_children.append(tree)
                for children in build_children(predecessor, table, prev_children):
                    yield children
                prev_children.pop()
        else:
            for children in build_children(predecessor, table, prev_children):
                yield children
    if not has_predecessor:
        yield prev_children

def qtree(node):
    # http://yohasebe.com/rsyntaxtree/
    if node.value.name == GAMMA_RULE:
        return qtree(node.children[0])

    # These are subtrees in parse tree.
    lhs = list(child.value.name for child in node.children)
    # These are non-terminals from the grammar.
    rhs = list(term.name for term in node.value.production if isinstance(term, Rule))

    assert lhs == rhs

    idx = 0
    parts = []

    for term in node.value.production:
        if isinstance(term, Rule):
            parts.append(qtree(node.children[idx]))
            idx += 1
        else:
            parts.append(term)

    return "[{0} {1}]".format(node.value.name, " ".join(parts))

################################################################################

def load_grammar(iterable):
    RE_TERMINAL = r"^[a-z]+$"
    RE_NON_TERMINAL = r"^[A-Z_/\\]+$"

    non_terminals = dict()
    starting_rule = None

    def get_term_and_semantics(n, part):
        if part.find(":") > 0:
            part, semantics = part.split(":", 1)
            if len(semantics) == 0 or semantics[0] not in [ ":", "=" ]:
                raise RuntimeError, "Malformed line #{0}: Invalid semantic expression for term '{1}'".format(n + 1, part)
            if semantics[0] == ":":
                try:
                    semantics = logic.parse_logic_expression(semantics[1:])
                except:
                    raise RuntimeError, "Malformed line #{0}: Unable to parse semantic expression for term '{1}'".format(n + 1, part)
            elif semantics[0] == "=":
                semantics = semantics[1:]
        else:
            semantics = logic_ast_nodes.Empty()
        if re.match(RE_TERMINAL, part):
            return part, semantics
        if re.match(RE_NON_TERMINAL, part):
            if part not in non_terminals:
                non_terminals[part] = Rule(part)
            return non_terminals[part], semantics
        raise RuntimeError, "(unreachable)"

    for n, line in enumerate(iterable):
        parts = line.strip().split()

        for part in parts:
            if part.find(":") > 0:
                part = part.split(":")[0]
            if not re.match(RE_TERMINAL, part) and not re.match(RE_NON_TERMINAL, part) and not part == "->" and not part == "!->":
                raise RuntimeError, "Malformed line #{0}: Unable to determine whether term '{1}' is a terminal or a non-terminal".format(n + 1, part)

        if len(parts) == 0:
            continue

        if len(parts) == 1:
            if parts[0] not in non_terminals:
                raise RuntimeError, "Malformed line #{0}: Unknown non-terminal '{1}'".format(n + 1, parts[0])
            else:
                starting_rule = parts[0]
                continue

        if parts[1] != "->" and parts[1] != "!->":
            raise RuntimeError, "Malformed line #{0}: Second part should be either '->' or '!->'".format(n + 1)

        if parts[1] == "->":
            safe_bindings = True
        else:
            safe_bindings = False

        lhs = get_term_and_semantics(n, parts[0])
        rhs = map(lambda x: get_term_and_semantics(n, x), parts[2:])

        if not isinstance(lhs[1], logic_ast_nodes.Node):
            raise RuntimeError, "Malformed line #{0}: Semantics for left-hand side should be either logic expression or nothing".format(n + 1)
        if not all(map(lambda x: isinstance(x[1], str) or isinstance(x[1], logic_ast_nodes.Empty), rhs)):
            raise RuntimeError, "Malformed line #{0}: Semantics for right-hand shide should be only variable bindings".format(n + 1)

        if not isinstance(lhs[0], Rule):
            raise RuntimeError, "Malformed line #{0}: Left-hand side have to be a non-terminal".format(n + 1)

        lhs[0].add(Production(lhs[1], *rhs, safe_bindings = safe_bindings))

    if starting_rule:
        return non_terminals[starting_rule]
    else:
        return non_terminals["S"]

################################################################################

if __name__ == "__main__":
    # You can specify grammar either by hard-coding it or by loading from file.
    # 
    # (Specifying grammar in code)
    #     SYM  = Rule("SYM", Production("a"))
    #     OP   = Rule("OP",  Production("+"), Production("*"))
    #     EXPR = Rule("EXPR")
    #     EXPR.add(Production(SYM))
    #     EXPR.add(Production(EXPR, OP, EXPR))
    #
    # (Loading grammar from file)
    #     g = load_grammar(open("a.txt"))


    parse_and_print(g, "john likes mary")
    parse_and_print(g, "john likes mary and hates ")
    parse_and_print(g, "mary hates john")
    parse_and_print(g, "whom does mary like")
    parse_and_print(g, "whom does mary like and hate")
    parse_and_print(g, "who likes mary")
    parse_and_print(g, "who likes mary and hates john")
