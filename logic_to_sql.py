#!/usr/bin/python
################################################################################

from collections import defaultdict
import operator

import logic_ast_nodes as nodes

class SqlGenerator:
    SYMBOL_MAPPING = {
        'Consists': 'my_consists',
        'Count': 'my_consists',
        'Is': 'my_is',
        'Takes': 'my_takes',
        'Have': 'my_have'
    }
    DIGIT_MAPPING = {
        'Ten': 10,
        'Twenty': 20
    }

    def __init__(self):
        self.type = None

        self.tables = list()
        self.variables = defaultdict(set)
        self.constraints = []

        self.stack = []

    def is_distinct_select(self, node):
            variables, body = node.uncurry()
            return\
            isinstance(node, nodes.Application) and\
            isinstance(node.argument, nodes.Lambda) and\
            isinstance(node.function, nodes.Symbol) and\
            (node.function.name == 'Distinctselect')

    def is_count(self, node):
        variables, body = node.uncurry()
        return\
        isinstance(node, nodes.Application) and\
        isinstance(node.argument, nodes.Lambda) and\
        isinstance(node.function, nodes.Symbol) and\
        (node.function.name == 'Count' or node.function.name == 'Sum')

    def is_exist(self, node):
        variables, body = node.uncurry()
        return\
        isinstance(node, nodes.Lambda) and\
        isinstance(body, nodes.Application) and\
        isinstance(body.argument, nodes.Symbol) and\
        isinstance(body.function, nodes.Application) and\
        isinstance(body.function.argument, nodes.Symbol) and\
        isinstance(variables, list) and\
        isinstance(variables[0], basestring)

    def is_insert(self, node):
        return\
        isinstance(node, nodes.Application) or\
        isinstance(node, nodes.Negation) or\
        isinstance(node, nodes.And) or\
        isinstance(node, nodes.Or)

    def is_select(self, node):
        return\
        isinstance(node, nodes.Lambda)

    def resolve_column(self, table, n):
        return "arg%d" % n

    def resolve_table(self, table):
        if isinstance(table, str):
            return str
        elif isinstance(table, nodes.Symbol):
            n = self.SYMBOL_MAPPING[table.name]
            t = "alias%d_%s" % (len(self.tables), n)
            self.tables.append((n, t))
            return t
        else:
            raise RuntimeError, "Unable to deduce table name from value: {0}".format(repr(table))

    def resolve_value(self, value):
        if isinstance(value, str):
            return repr(value)
        elif isinstance(value, tuple):
            assert(len(value) >= 2)
            return "%s.%s" % (value[0], self.resolve_column(value[0], value[1]))
        elif isinstance(value, nodes.Symbol):
            if self.DIGIT_MAPPING.has_key(value.name):
                return repr(self.DIGIT_MAPPING[value.name])
            else:
                return repr(value.name)
        else:
            raise RuntimeError, "Unable to deduce table name from value: {0}".format(repr(value))

    def _visit_function(self, node):
        if isinstance(node, nodes.Application):
            table, values = node.uncurry()

            table = self.resolve_table(table)

            for n, value in enumerate(values):
                if isinstance(value, nodes.Symbol):
                    self.constraints.append((table, n, value))
                elif isinstance(value, nodes.Variable):
                    self.variables[value.name].add((table, n))
        elif isinstance(node, nodes.And):
            node.visit(self._visit_function, self._visit_combinator, None)
        elif isinstance(node, nodes.Not):
            raise RuntimeError, "'Not' clauses are not supported currently."
        elif isinstance(node, nodes.Or):
            raise RuntimeError, "'Or' clauses are not supported currently."
        else:
            raise RuntimeError, "Unsupported node: {0}".format(repr(node))

    def _visit_combinator(self, *args):
        pass

    def _induce_variable_constraints(self):
        for variable in self.variables:
            variable_constraints = list(self.variables[variable])
            for lhs, rhs in zip(variable_constraints[0:], variable_constraints[1:]):
                self.constraints.append((lhs[0], lhs[1], rhs))

    def make_insert(self, node):
        self.type = "INSERT"
        self._visit_combinator(self._visit_function(node))

        original_table_names = set(map(operator.itemgetter(0), self.tables))
        mapped_table_names = set(map(operator.itemgetter(1), self.tables))

        if len(original_table_names) != len(mapped_table_names):
            raise RuntimeError, "Expression is too complex to be converted into a single insert statement."

        reverse_table_mapping = dict(map(lambda x: (x[1], x[0]), self.tables))

        inserted_values = defaultdict(list)

        for table, column, value in self.constraints:
            inserted_values[table].append((self.resolve_column(table, column), self.resolve_value(value)))
        for table in inserted_values.iterkeys():
            columns_and_values = inserted_values[table]

            columns = map(operator.itemgetter(0), columns_and_values)
            values = map(operator.itemgetter(1), columns_and_values)

            table_clause = "%s(%s)" % (reverse_table_mapping[table], ", ".join(columns))
            values_clause = "(%s)" % (", ".join(values))

            yield "INSERT INTO %s VALUES %s" % (table_clause, values_clause)

    def make_is_exist(self, node):
        self.type = "SELECT"

        variables, body = node.uncurry()

        self._visit_combinator(self._visit_function(body))
        self._induce_variable_constraints()

        from_clause = ", ".join(map(
            lambda t: "%s AS %s" % t,
            self.tables))

        where_clause = " AND ".join(map(
            lambda c: "%s = %s" % (self.resolve_value(c[0:2]), self.resolve_value(c[2])),
            self.constraints))

        yield "SELECT CASE WHEN count(*)=0 THEN 'NO' ELSE 'YES' END FROM {0} WHERE {1}".format(from_clause,
            where_clause)

    def make_select(self, node):
        self.type = "SELECT"

        variables, body = node.uncurry()

        self._visit_combinator(self._visit_function(body))
        self._induce_variable_constraints()

        result_clause = ", ".join(map(
            lambda kv: "%s AS %s" % (self.resolve_value(list(kv[1])[0]), kv[0]),
            self.variables.items()))
        from_clause = ", ".join(map(
            lambda t: "%s AS %s" % t,
            self.tables))
        where_clause = " AND ".join(map(
            lambda c: "%s = %s" % (self.resolve_value(c[0:2]), self.resolve_value(c[2])),
            self.constraints))
        yield "SELECT {0} FROM {1} WHERE {2}".format(result_clause, from_clause, where_clause)

    def make_distinct_select(self, node):
        variables, body = node.argument.uncurry()
        from_clause = self.SYMBOL_MAPPING[body.function.function.name]
        yield "SELECT {0} FROM {1}".format("DISTINCT arg1", from_clause)

    # generating a 'count' query
    def make_count(self, node):
        self.type = "SELECT"

        variables, body = node.argument.uncurry()

        if len(variables) == 2:
            from_clause = self.SYMBOL_MAPPING[body.function.function.name]
            yield "SELECT {0} FROM {1}".format("COUNT(DISTINCT arg0)", from_clause)
        else:
            self._visit_combinator(self._visit_function(body))

            self._induce_variable_constraints()

            group_count = 'COUNT'

            if node.function.name == 'Sum':
                group_count = 'Sum'

            result_clause = ", ".join(map(
                lambda kv: group_count + "(%s) AS %s" % (self.resolve_value(list(kv[1])[0]), kv[0]),
                self.variables.items()))
            from_clause = ", ".join(map(
                lambda t: "%s AS %s" % t,
                self.tables))

            where_clause = " AND ".join(map(
                lambda c: "%s = %s" % (self.resolve_value(c[0:2]), self.resolve_value(c[2])),
                self.constraints))
            yield "SELECT {0} FROM {1} WHERE {2}".format(result_clause, from_clause, where_clause)

    def make_sql(self, node):
        generator = None
        if self.is_distinct_select(node):
            generator = self.make_distinct_select(node)
        elif self.is_count(node):
            generator = self.make_count(node)
        elif self.is_exist(node):
            generator = self.make_is_exist(node)
        elif self.is_insert(node):
            generator = self.make_insert(node)
        elif self.is_select(node):
            generator = self.make_select(node)
        else:
            raise RuntimeError, "Unable to determine SQL query type; probably expression is too complex."

        for item in generator:
            yield item
