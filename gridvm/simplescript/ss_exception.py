def reverse_find(haystack, needle, index):
    while index > 0:
        if haystack[index] == needle:
            return index
        index -= 1
    else:
        return -1


class CodeException(Exception):
    def __init__(self, source, pos, lineno, total, message):
        start = reverse_find(source, '\n', pos-1)
        end = source.find('\n', pos-1)
        col_index = pos - start

        if col_index == 1:
            #error happened in previous line
            lineno -= 1
            end = start - 1
            start = reverse_find(source, '\n', start-2)
            col_index = end-start

        line = source[start:end]

        self.coord = (lineno, col_index)
        self.line = line
        self.text = source

        exception_body =\
            '\nIn line {0}, near column {1}:\n\n {2}\n{3}{4}\n\n{5}'.format(
                lineno,
                col_index-1,
                line.replace('\t', ' '),
                ' ' * (col_index-1),
                '^',
                message
            )
        super().__init__(exception_body)

class GeneratorException(Exception):
    def __init__(self, line_no, cause):
        super().__init__('Error at line {}: {}'.format(line_no, cause))

class CodeObjectException(Exception):
    def __init__(self, exception, *args, **kwargs):
        super().__init__('Cannot load Code Object:[{}] - {}'.format(
            exception.__class__.__name__, str(exception)), *args, **kwargs)
