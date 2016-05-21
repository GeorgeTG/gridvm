import itertools
import sys

TEMPLATE=\
r'''from enum import IntEnum, unique

@unique
class OpCode(IntEnum):
'''

def iter_words(filepath):
    with open(filepath, 'r') as f:
        for word in itertools.chain( *(line.split() for line in f) ):
            yield word

def iter_capital_words(filepath):
    for word in iter_words(filepath):
        if word.isupper():
            yield word

def main():
    src = TEMPLATE
    for i, word in enumerate(iter_capital_words(sys.argv[1])):
        src += '    {} = {}\n'.format(word.ljust(12), i)
    print(src)

if __name__ == '__main__':
    main()
