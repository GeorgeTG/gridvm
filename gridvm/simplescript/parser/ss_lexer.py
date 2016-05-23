from ply import lex
from ..ss_exception import CodeException

class SimpleScriptLexer(object):

    def __init__(self):
        self.lexer = None

    def build(self, **kwargs):
        self.lexer = lex.lex(object=self, **kwargs)

    def input(self, text):
        self.lexer.input(text)

    def token(self):
        self.last_token = self.lexer.token()
        return self.last_token

    def lineno(self):
        return self.lexer.lineno

    tokens = [ 'VARNAME', 'LBRACKET', 'RBRACKET', 'STR',
         'NEWLINE', 'NUMBER', 'LABEL', 'TAG', 'RET',
         'BRANCH', 'SET', 'ARITHM', 'SYS', 'RCV', 'SND']

    t_ignore = ' \t'
    t_VARNAME = r'\$[a-zA-Z][a-zA-Z0-9_]*'
    t_LBRACKET = r'\['
    t_RBRACKET = r'\]'
    t_TAG = '\#SIMPLESCRIPT'

    # TODO: Fix this MESS
    def t_ID(self, t):
        r'[A-Z][A-Z0-9]+'
        if t.value.startswith('L'):
            t.type = 'LABEL'
        elif t.value.startswith('B'):
            t.type = 'BRANCH'
        elif t.value in ['SLP', 'PRN']:
            t.type = 'SYS'
        elif t.value == 'SND':
            t.type = 'SND'
        elif t.value == 'RCV':
            t.type = 'RCV'
        elif t.value == 'SET':
            t.type = 'SET'
        elif t.value == 'RET':
            t.type = 'RET'
        else:
            t.type = 'ARITHM'

        return t

    def t_NEWLINE(self, t):
        r'\n[ \t\n]*'
        t.lexer.lineno += t.value.count("\n")
        return t

    def  t_STR(self, t):
        r'".+"'
        t.value = t.value[1:-1]
        return t

    def t_NUMBER(self, t):
        r'-?\d+'
        t.value = int(t.value)
        return t

    def t_error(self, p):
        total = p.lexer.lexpos
        source = p.lexer.lexdata
        pos = p.lexer.lexpos
        lineno = p.lexer.lineno

        if ord(p.value[0]) == ord('\n'):
            val = '\\n'
        else:
            val = source[pos]

        message = 'Unexpected character: {}'.format(val)

        raise CodeException(source, pos, lineno, total, message)
