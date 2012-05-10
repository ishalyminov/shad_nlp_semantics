#!/usr/bin/python
################################################################################

__all__ = [ 'parse_logic_expression' ]

import copy

from pyparsing import *

try:
    ParserElement.enablePackrat()
except:
    pass

DEBUG = False

################################################################################
# Semantics

import logic_ast_nodes as nodes

def on_individual_variable(string, location, tokens):
    assert(len(tokens) == 1)
    return nodes.Variable(*tokens)

def on_functional_variable(string, location, tokens):
    assert(len(tokens) == 1)
    return nodes.Variable(*tokens)

def on_symbol(string, location, tokens):
    assert(len(tokens) == 1)
    return nodes.Symbol(*tokens)

def on_application_expression(string, location, tokens):
    return reduce(nodes.Application, tokens)

def on_lambda_expression(string, location, tokens):
    assert(len(tokens) == 2)
    return nodes.Lambda(*tokens)

def on_formula_expression(string, location, tokens):
    operand_stack = []
    connective_stack = []
    connective_priorities = { '!' : 2, '&&' : 1, '||' : 0 }

    def is_connective(token):
        return token in connective_priorities.keys()

    def can_push_on_connective_stack(token):
        return len(connective_stack) == 0 or connective_priorities[token] > connective_priorities[connective_stack[-1]]

    def fold_connective_stack():
        top_connective = connective_stack.pop()
        if top_connective == '!':
            assert(len(operand_stack) >= 1)
            operand_stack.append(nodes.Negation(operand_stack.pop()))
        elif top_connective == '&&':
            assert(len(operand_stack) >= 2)
            rhs = operand_stack.pop()
            lhs = operand_stack.pop()
            operand_stack.append(nodes.And(lhs, rhs))
        elif top_connective == '||':
            assert(len(operand_stack) >= 2)
            rhs = operand_stack.pop()
            lhs = operand_stack.pop()
            operand_stack.append(nodes.Or(lhs, rhs))

    while len(tokens) > 0:
        current = tokens.pop(0)
        if is_connective(current):
            while not can_push_on_connective_stack(current):
                fold_connective_stack()
            connective_stack.append(current)
        else:
            operand_stack.append(current)

    while len(connective_stack) > 0:
        fold_connective_stack()

    assert(len(operand_stack) == 1)
    return operand_stack.pop()


################################################################################
# Lexical Level

UPPERCASE_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWERCASE_LETTERS = "abcdefghijklmnopqrstuvwxyz"

JustIndividualVariable = Word(LOWERCASE_LETTERS, exact = 1)
JustFunctionalVariable = Word(UPPERCASE_LETTERS, exact = 1)

IndividualVariable = copy.deepcopy(JustIndividualVariable)
IndividualVariable.setParseAction(on_individual_variable)
FunctionalVariable = copy.deepcopy(JustFunctionalVariable)
FunctionalVariable.setParseAction(on_functional_variable)

Symbol = Word(UPPERCASE_LETTERS, LOWERCASE_LETTERS, min = 2, max = 0, asKeyword = True)
Symbol.setParseAction(on_symbol)

LeftP  = Suppress("(")
RightP = Suppress(")")

################################################################################
# Syntactical Level

Expression = Forward()
ApplicationExpression = Forward()
ApplicationExpression.setParseAction(on_application_expression)
AtomicExpression = Forward()
FormulaExpression = Forward()
FormulaExpression.setParseAction(on_formula_expression)
LambdaExpression = Forward()
LambdaExpression.setParseAction(on_lambda_expression)
ParenthesizedExpression = Forward()

ApplicationExpression << (
    ( ParenthesizedExpression | Symbol | IndividualVariable | FunctionalVariable )
    +
    OneOrMore(
        ( LeftP + AtomicExpression + ZeroOrMore(Suppress(",") + AtomicExpression) + RightP )
        | ParenthesizedExpression
    )
)

AtomicExpression << (
    ( ApplicationExpression | Symbol | IndividualVariable | FunctionalVariable )
)

FormulaExpression << (
    Optional("!") + AtomicExpression + ZeroOrMore( oneOf("&& ||") + FormulaExpression )
    | LeftP + FormulaExpression + RightP
)

LambdaExpression << (
    Suppress("\\") + (JustIndividualVariable | JustFunctionalVariable) + Suppress(".") + Expression
)

ParenthesizedExpression << (
    LeftP + Expression + RightP
)

Expression << (
    FormulaExpression | LambdaExpression | ParenthesizedExpression
)

Expression.setName("expression")
ApplicationExpression.setName("application_expression")
AtomicExpression.setName("atomic_expression")
FormulaExpression.setName("formula_expression")
LambdaExpression.setName("binding_expression")
ParenthesizedExpression.setName("parenthesized_expression")

if DEBUG:
    Expression.setDebug(True)
    ApplicationExpression.setDebug(True)
    AtomicExpression.setDebug(True)
    FormulaExpression.setDebug(True)
    LambdaExpression.setDebug(True)
    ParenthesizedExpression.setDebug(True)

def parse_logic_expression(string):
    result = Expression.parseString(string, parseAll = True)
    assert(len(result) == 1)
    assert(True)#Check type
    return result[0]
