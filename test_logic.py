import unittest

import logic
import logic_ast_nodes as nodes

class LogicTest(unittest.TestCase):
    def test_parse_logic_expression(self):
        for string in [
            r"(P)(Q)",
            r"John",
            r"(John)",
            r"Man(x)",
            r"!Man(x)",
            r"(Man(x) && Tall(x) && Walks(x))",
            r"(\x.Man(x))",
            r"(\x.Man(x))(John)",
            r"\x.\y.Sees(x,y)",
            r"(\x.\y.Sees(x,y))(a,b)",
            r"P(x) && P(y)",
            r"P(x) && Q(y) && R(z)",
            r"Q(x) || Q(y)",
            r"\P.\Q.P(x) && Q(x)",
            r"\P.\Q.(P(x) && Q(x))",
            r"(\x.\y.Likes(x,y))(John)(Mary)",
            r"(\x.\y.Likes(x,y))(John, Mary)",
            r"(\P.\Q.(P(x) && Q(x)))(\x.Dog(x))(\x.Bark(x))"
            ]:
            try:
                x = logic.parse_logic_expression(string)
                y = logic.parse_logic_expression(str(x))
            except:
                raise AssertionError, "Failed to parse '{0}'".format(string)
            self.assertEquals(x, y)
            self.assertEquals(str(x), str(y))

    def test_free_variables(self):
        def test(source, variables):
            x = logic.parse_logic_expression(source)
            y = list(variables)
            self.assertEqual(set(y), x.free_variables())

        test(r"(\x.Man(x))", "")
        test(r"P(x) && Q(y) && R(z)", "xyzPQR")
        test(r"(\P.\Q.(P(x) && Q(y)))(\x.Dog(x))(\x.Bark(x))", "xy")

    def test_replace_variable(self):
        def test(source, variable, replacement, result):
            x = logic.parse_logic_expression(source)
            y = logic.parse_logic_expression(replacement)
            z = str(result)
            self.assertEquals(z, str(x.replace_variable(variable, y)))

        self.assertEquals(r"Q(x)", str(logic.parse_logic_expression(r"P(x)").replace_variable("P", nodes.Variable("Q"))))
        
        test(r"P(x,y,z)", "x", "y", r"P(y,y,z)")
        test(r"(\x.P(x,y))(P(x,y))", "x", "z", r"(\x.P(x,y))(P(z,y))")
        test(r"(\y.(\x.P(x,y,z))(x))", "x", "z", r"(\y.(\x.P(x,y,z))(z))")

        test(r"(\y.(\x.P(x,y,z))(x))", "z", "x", r"(\y.(\x'.P(x',y,x))(x))")

    def test_replace_with_bindings(self):
        def test(source, bindings, result):
            x = logic.parse_logic_expression(source)
            y = dict(map(lambda x: (x[0], logic.parse_logic_expression(x[1])), bindings.items()))
            z = str(result)
            self.assertEquals(z, str(x.replace_with_bindings(y)))

        test(r"(P)(Q)", { "P" : r"\x.Man(x)", "Q" : r"\x.Red(x)" }, r"(\x.Man(x))(\x.Red(x))")

    def test_simplify(self):
        def test(source, result):
            x = logic.parse_logic_expression(source)
            y = logic.parse_logic_expression(result)
            self.assertEquals(str(y), str(x.simplify()))

        test(r"(\x.\y.Likes(x,y))(John)(Mary)", r"Likes(John,Mary)")
        test(r"(\P.P)(\z.(\x.(\y.Likes(y,x)))(z)(Mary))", r"(\z.Likes(Mary,z))")
        test(r"(\P.P)((\x.(\y.Likes(y,x)))(Mary))", r"(\y.Likes(y,Mary))")
        test(r"(\P.P)(\x.(\x.(\y.Likes(y,x)))(Mary)(x) && (\x.(\y.Hates(y,x)))(John)(x))", r"(\x.Likes(x,Mary)&&Hates(x,John)))")

if __name__ == '__main__':
    unittest.main()
