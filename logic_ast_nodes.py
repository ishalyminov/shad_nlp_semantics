################################################################################
# AST Nodes

import operator

class Node(object):
    def __init__(self):
        pass
    def __str__(self):
        raise NotImplementedError
    def __repr__(self):
        raise NotImplementedError
    def __eq__(self, other):
        raise NotImplementedError
    def __hash__(self):
        raise NotImplementedError
    def visit(self, function, combinator, value):
        raise NotImplementedError
    def free_variables(self):
        return self.visit(
            lambda node: node.free_variables(),
            lambda *args: reduce(operator.or_, args),
            set())
    def replace_variable(self, variable, expression, with_alpha_conversion = True):
        return self.visit(
            lambda node: node.replace_variable(variable, expression, with_alpha_conversion),
            lambda *args: self.__class__(*args),
            None)
    def replace_with_bindings(self, bindings, with_alpha_conversion = True):
        node = self
        for variable in node.free_variables():
            if variable in bindings:
                expression = bindings[variable]
                expression = expression.replace_with_bindings(bindings, with_alpha_conversion)
                node = node.replace_variable(variable, expression, with_alpha_conversion)
        return node
    def simplify(self):
        return self.visit(
            lambda node: isinstance(node, Node) and node.simplify() or node,
            lambda *args: self.__class__(*args),
            None)

class Empty(Node):
    def __init__(self,):
        super(Empty, self).__init__()
    def __str__(self):
        return ""
    def __repr__(self):
        return "Empty()" 
    def __eq__(self, other):
        if not isinstance(other, Empty):
            return False
        return True
    def __hash__(self):
        return hash(id(self))
    def visit(self, function, combinator, value):
        return value
    def replace_variable(self, variable, expression, with_alpha_conversion = True):
        return self
    def simplify(self):
        return self

class Symbol(Node):
    def __init__(self, name):
        super(Symbol, self).__init__()
        self.name = name
    def __str__(self):
        return str(self.name)
    def __repr__(self):
        return "Symbol(%s)" % repr(self.name)
    def __eq__(self, other):
        if not isinstance(other, Symbol):
            return False
        return (self.name) == (other.name)
    def __hash__(self):
        return hash((self.name))
    def visit(self, function, combinator, value):
        return value
    def replace_variable(self, variable, expression, with_alpha_conversion = True):
        return self
    def simplify(self):
        return self

class Variable(Node):
    def __init__(self, name):
        super(Variable, self).__init__()
        self.name = name
    def __str__(self):
        return str(self.name)
    def __repr__(self):
        return "Variable(%s)" % repr(self.name)
    def __eq__(self, other):
        if not isinstance(other, Variable):
            return False
        return (self.name) == (other.name)
    def __hash__(self):
        return hash((self.name))
    def visit(self, function, combinator, value):
        return value
    def free_variables(self):
        return set([self.name])
    def replace_variable(self, variable, expression, with_alpha_conversion = True):
        return expression if self.name == variable else self
    def simplify(self):
        return self

class Application(Node):
    def __init__(self, function, argument):
        super(Application, self).__init__()
        self.function = function
        self.argument = argument
    def __str__(self):
        function, arguments = self.uncurry()
        if all(map(lambda x: isinstance(x, Variable) and x.name.upper() == x.name, arguments)):
            parenthesize_function = True
            parenthesize_arguments = True
            function = str(function)
            arguments = ")(".join(str(argument) for argument in arguments)
        elif isinstance(function, Symbol) or isinstance(function, Variable):
            parenthesize_function = False
            parenthesize_arguments = True
            function = str(function)
            arguments = ",".join(str(argument) for argument in arguments)
        else:
            parenthesize_function = False
            parenthesize_arguments = not isinstance(self.argument, Lambda)
            function = str(self.function)
            arguments = str(self.argument)
        if parenthesize_function:
            function = "(" + function + ")"
        if parenthesize_arguments:
            arguments = "(" + arguments + ")"
        return function + arguments
    def __repr__(self):
        return "Application(%s, %s)" % (repr(self.function), repr(self.argument))
    def __eq__(self, other):
        if not isinstance(other, Application):
            return False
        return (self.function, self.argument) == (other.function, other.argument)
    def __hash__(self):
        return hash((self.function, self.argument))
    def visit(self, function, combinator, value):
        return combinator(function(self.function), function(self.argument))
    def simplify(self):
        function = self.function.simplify()
        argument = self.argument.simplify()
        if isinstance(function, Lambda):
            return function.body.replace_variable(function.variable, argument).simplify()
        else:
            return self.__class__(function, argument)
    def uncurry(self):
        function = self.function
        arguments = [ self.argument ]
        while isinstance(function, Application):
            arguments.insert(0, function.argument)
            function = function.function
        return (function, arguments)

class Lambda(Node):
    def __init__(self, variable, body):
        super(Lambda, self).__init__()
        self.variable = variable
        self.body = body
    def __str__(self):
        return "(\\%s.%s)" % (str(self.variable), str(self.body))
    def __repr__(self):
        return "Lambda(%s, %s)" % (repr(self.variable), repr(self.body))
    def __eq__(self, other):
        if not isinstance(other, Lambda):
            return False
        return (self.variable, self.body) == (other.variable, other.body)
    def __hash__(self):
        return hash((self.variable, self.body))
    def visit(self, function, combinator, value):
        return combinator(function(self.variable), function(self.body))
    def free_variables(self):
        return self.body.free_variables() - set([self.variable])
    def replace_variable(self, variable, expression, with_alpha_conversion = True):
        if self.variable == variable:
            return self
        else:
            alpha_converted_variable = self.variable
            while with_alpha_conversion and alpha_converted_variable in expression.free_variables():
                alpha_converted_variable += "'"
            if self.variable == alpha_converted_variable:
                return self.__class__(
                    self.variable,
                    self.body.replace_variable(variable, expression))
            else:
                return self.__class__(
                    alpha_converted_variable,
                    self.body \
                        .replace_variable(self.variable, Variable(alpha_converted_variable)) \
                        .replace_variable(variable, expression))
    def uncurry(self):
        variables = [ self.variable ]
        body = self.body
        while isinstance(body, Lambda):
            variables.append(body.variable)
            body = body.body
        return (variables, body)

class Negation(Node):
    def __init__(self, body):
        super(Negation, self).__init__()
        self.body = body
    def __str__(self):
        return "!%s" % str(self.body)
    def __repr__(self):
        return "Negation(%s)" % repr(self.body)
    def __eq__(self, other):
        if not isinstance(other, Negation):
            return False
        return (self.body) == (other.body)
    def __hash__(self):
        return hash((self.body))
    def visit(self, function, combinator, value):
        return combinator(function(self.body))

class And(Node):
    def __init__(self, lhs, rhs):
        super(And, self).__init__()
        self.lhs = lhs
        self.rhs = rhs
    def __str__(self):
        return "%s && %s" % (str(self.lhs), str(self.rhs))
    def __repr__(self):
        return "And(%s, %s)" % (repr(self.lhs), repr(self.rhs))
    def __eq__(self, other):
        if not isinstance(other, And):
            return False
        return (self.lhs, self.rhs) == (other.lhs, other.rhs)
    def __hash__(self):
        return hash((self.lhs, self.rhs))
    def visit(self, function, combinator, value):
        return combinator(function(self.lhs), function(self.rhs))

class Or(Node):
    def __init__(self, lhs, rhs):
        super(Or, self).__init__()
        self.lhs = lhs
        self.rhs = rhs
    def __str__(self):
        return "%s || %s" % (str(self.lhs), str(self.rhs))
    def __repr__(self):
        return "Or(%s, %s)" % (repr(self.lhs), repr(self.rhs))
    def __eq__(self, other):
        if not isinstance(other, Or):
            return False
        return (self.lhs, self.rhs) == (other.lhs, other.rhs)
    def __hash__(self):
        return hash((self.lhs, self.rhs))
    def visit(self, function, combinator, value):
        return combinator(function(self.lhs), function(self.rhs))
