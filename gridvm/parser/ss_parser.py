from .ss_lexer import SimpleScriptLexer

from ply import yacc

class SimpleScriptParser(object):

    code = []
    labels = []

    def __init__(
        self,
        lex_optimize=True,
        lextab='ssparser.lextab',
        yacc_optimize=True,
        yacctab='ssparser.yacctab',
        yacc_debug=False,
        taboutputdir=''):

        self.sslex = SimpleScriptLexer()

        self.sslex.build(
            optimize=lex_optimize,
            lextab=lextab,
            outputdir=taboutputdir)

        self.tokens = self.sslex.tokens

        self.ssparser = yacc.yacc(
            module=self,
            start='tag',
            debug=yacc_debug,
            optimize=yacc_optimize,
            tabmodule=yacctab,
            outputdir=taboutputdir)

    def p_tag(self, p):
        """ tag : TAG NEWLINE program"""
        pass

    def p_program(self, p):
        """ program : program label_or_statement
                    | label_or_statement"""
        pass

    def p_label_or_statement(self, p):
        """ label_or_statement : LABEL
                               | statement NEWLINE"""
        if isinstance(p[1], str):
            self.labels.append(p[1])
        p[0] = p[1]

    def p_statement(self, p):
        """ statement : arithm
                      | sys
                      | net
                      | ret
                      | set
                      | branch"""
        self.code.append(p[1])
        p[0] = p[1]

    def p_set(self, p):
        """ set : SET var varval """
        p[0] = (p[1], p[2], p[3])

    def p_net(self, p):
        """ net : rcv
                | snd"""
        p[0] = p[1]

    def p_snd(self, p):
        """ snd : SND varval varval"""
        p[0] = (p[1], p[2])

    def p_rcv(self, p):
        """ rcv : RCV varval var"""
        p[0] = (p[1], p[2])

    def p_varvals(self, p):
        """ varvals : varvals varval
                    | varval"""
        if len(p) == 3:
            if isinstance(p[1], tuple):
                p[0] = p[1] + (p[2],)
            else:
                p[0] = (p[1], p[2])
        else:
            p[0] = p[1]

    def p_ret(self, p):
        """ ret : RET"""
        p[0] = p[1]

    def p_sys(self, p):
        """ sys : SYS varval
                | SYS STR varvals
                | SYS STR
                | SYS LABEL """
        if len(p) == 3:
            p[0] = (p[1], p[2])
        elif len(p) == 4:
            p[0] = (p[1], p[2], p[3])
        else:
            p[0] = p[1]

    def p_branch(self, p):
        """ branch : BRANCH varval varval LABEL
                   | BRANCH LABEL """
        if len(p) == 5:
            p[0] = (p[1], p[2], p[3], p[4])
        else:
            p[0] = (p[1], p[2])

    def p_artihm(self, p):
        """ arithm : ARITHM var varval varval """
        p[0] = (p[1], p[2], p[3])

    def p_array(self, p):
        """ array : VARNAME LBRACKET varval RBRACKET"""
        p[0] = (p[1], p[3])

    def p_var(self, p):
        """ var : VARNAME
                | array"""
        p[0] = p[1]

    def p_varval(self, p):
        """ varval : var
                   | NUMBER"""
        p[0] = p[1]

    def reverse_find(haystack, needle, index):
        while index != 0:
            if haystack[index] == needle:
                return index
            index -= 1

    def p_error(self, p):
        source = p.lexer.lexdata
        pos = p.lexer.lexpos

        start = reverse_find(source, '\n', pos)
        end = source.find('\n', pos)

        line = source[start:end]
        col_index = pos - start

        exception_body =\
            '\nIn line {0}, near column {1}:\n\n {2}\n{3}{4}\n\n{5}'.format(
                p.lexer.lineno,
                col_index,
                line.replace('\t', ' '),
                ' ' * col_index,
                '^',
                'Unexpected token: {} [{}]'.format(p.value, p.type)
            )
        raise Exception(exception_body)

    def parse(self, text, debuglevel=0):
        self.ssparser.parse(
            input=text,
            lexer=self.sslex,
            debug=debuglevel)
        return self.code

if __name__ == '__main__':
    import sys
    with open(sys.argv[1], 'r') as f:
        b = f.read()
    parser = SimpleScriptParser()
    code = parser.parse(b)

    for line in code:
        print(line)
    print(parser.labels)
