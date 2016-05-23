from pathlib import Path

from .ss_lexer import SimpleScriptLexer
from .ss_ast import *
from ..ss_exception import CodeException

from ply import yacc


class SimpleScriptParser(object):

    labels_defs = {}

    def __init__(
        self,
        lex_optimize=True,
        lextab='sslex.lextab',
        yacc_optimize=True,
        yacctab='ssparser.yacctab',
        yacc_debug=False,
        taboutputdir=''):

        file_dir = Path(__file__).parent
        if not lextab:
            lextab = str(file_dir / 'ssparser.lextab')
        if not yacctab:
            yacctab = str(file_dir / 'ssparser.yacctab')

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
        """ tag : TAG NEWLINE program
                | """

        if len(p) != 4:
            p[0] = Program([])
        else:
            p[0] = Program(p[3])

    def p_program(self, p):
        """ program : program statement
                    | statement"""
        if len(p) == 3:
            p[0] = p[1] + (p[2],)
        else:
            p[0] = (p[1],)

    def p_labeled_statement(self, p):
        """ statement : LABEL operation NEWLINE"""
        p[0] = Statement(p[2], LabelDef(p[1]), coord=p.lexer.lineno())

    def p_statement(self, p):
        """ statement : operation NEWLINE"""
        p[0] = Statement(p[1], None, coord=p.lexer.lineno())

    def p_operation(self, p):
        """ operation : arithm
                      | sys
                      | net
                      | ret
                      | set
                      | branch"""
        p[0] = p[1]

    def p_set(self, p):
        """ set : SET var varval """
        p[0] = SetOperation(p[1], p[2], p[3], coord=p.lexer.lineno())

    def p_net(self, p):
        """ net : rcv
                | snd"""
        p[0] = p[1]

    def p_snd(self, p):
        """ snd : SND varval varval"""
        p[0] = NetOperation(p[1], p[2], p[3], coord=p.lexer.lineno())

    def p_rcv(self, p):
        """ rcv : RCV varval var"""
        p[0] = NetOperation(p[1], p[2], p[3], coord=p.lexer.lineno())

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
        p[0] = Ret(coord=p.lexer.lineno())

    def p_sys_slp(self, p):
        """ sys : SYS varval """
        p[0] = SleepOperation(p[2], coord=p.lexer.lineno())

    def p_sys_prn_no_vect(self, p):
        """ sys : SYS STR"""
        p[0] = PrintOperation(p[2], None, coord=p.lexer.lineno())

    def p_sys_prn(self, p):
        """ sys : SYS STR varvals"""
        if not isinstance(p[3], tuple):
            p[0] = PrintOperation(p[2], (p[3],), coord=p.lexer.lineno())
        else:
            p[0] = PrintOperation(p[2], p[3], coord=p.lexer.lineno())

    def p_branch(self, p):
        """ branch : BRANCH varval varval LABEL
                   | BRANCH LABEL """
        if len(p) == 5:
            p[0] = BranchOperation(p[1], p[2], p[3], LabelRef(p[4]), coord=p.lexer.lineno())
        else:
            p[0] = BranchOperation(p[1], None, None, LabelRef(p[2], coord=p.lexer.lineno()),
                    coord=p.lexer.lineno())

    def p_artihm(self, p):
        """ arithm : ARITHM var varval varval """
        p[0] = ArithmOperation(p[1], p[2], p[3], p[4], coord=p.lexer.lineno())

    def p_array(self, p):
        """ array : VARNAME LBRACKET varval RBRACKET"""
        p[0] = ArrayAccess(p[1], p[3], coord=p.lexer.lineno())

    def p_var(self, p):
        """ var : VARNAME
                | array"""
        if isinstance(p[1], ArrayAccess):
            p[0] = p[1]
        else:
            p[0] = VarAccess(p[1], coord=p.lexer.lineno())

    def p_varval(self, p):
        """ varval : var
                   | NUMBER"""
        if isinstance(p[1], int):
            p[0] = Constant(p[1], coord=p.lexer.lineno())
        else:
            p[0] = p[1]

    def p_error(self, p):
        source = p.lexer.lexdata
        pos = p.lexer.lexpos
        total = p.lexer.lexpos
        lineno = p.lexer.lineno

        if ord(p.value[0]) == ord('\n'):
            val = '\\n'
        else:
            val = p.value

        message = 'Unexpected token: {} [{}]'.format(val, p.type)
        raise CodeException(source, pos, lineno, total, message)


    def parse(self, text, debuglevel=0):
        return self.ssparser.parse(
            input=text,
            lexer=self.sslex,
            debug=debuglevel)

if __name__ == '__main__':
    import sys
    with open(sys.argv[1], 'r') as f:
        b = f.read()
    parser = SimpleScriptParser()
    code = parser.parse(b)
    code.show()
