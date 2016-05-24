from pathlib import Path

from ..parser.ss_parser import SimpleScriptParser
from ..codegen.ss_generator import SimpleScriptGenerator
from ..codegen.ss_code import SimpleScriptCodeObject
from ..codegen.ss_bcode import OpCode, Operation
from .utils import fast_hash

SKIP_OBJECT_FILE_SIZE = 600

def generic_load(filename, **kwargs):
    filepath = Path(filename).resolve()
    if filepath.suffix == '.ssc':
        return load_code_object_file(filename, **kwargs)
    elif filepath.suffix == '.ss':
        return load_source(filename, **kwargs)

def load_code_object_file(filename):
    return SimpleScriptCodeObject.from_file(filename, decompress=True)

def _just_load(source_file):
    with source_file.open('r') as f:
        source = f.read()

    # parse source into tree
    parser = SimpleScriptParser()
    tree = parser.parse(source)

    # generate bytecode
    gen = SimpleScriptGenerator()
    return gen.generate(tree)

def load_source(filename, dump_to_objet_file=True):
    source_file = Path(filename).resolve()
    stat = source_file.stat()
    source_ts = stat.st_mtime

    if not dump_to_objet_file or stat.st_size < SKIP_OBJECT_FILE_SIZE:
        # don't dump to object file
        return _just_load(source_file)

    # myprogram.ss -> .myprogram.ssc
    name = source_file.stem
    code_object = source_file.parent / ('.' + name + '.ssc')

    if code_object.is_file() and code_object.stat().st_mtime > source_ts:
        # code object file must exist and be newer than source to be up to date
        return load_code_object(str(code_object))
    else:
        # outdated or non-existant code object
        print('Building bytecode')
        with source_file.open('r') as f:
            source = f.read()

        # parse source into tree
        parser = SimpleScriptParser()
        tree = parser.parse(source)

        # generate bytecode
        gen = SimpleScriptGenerator()
        code = gen.generate(tree)

        # save for future use
        code.to_file(str(code_object), compress=True)
        return code



MT_TAG = "#SIMPLESCRIPT_MULTITHREADED"
T_TAG = "#THREAD"
class ThreadInfo(object):
    def __init__(self, program_id, id, source_file, args):
        self.source_file = source_file
        self.id = id
        self.program_id = program_id
        self.args = args

class ProgramInfo(object):
    def __init__(self, filename):
        self._filepath = Path(filename).resolve()
        self._program_id = fast_hash(str(self._filepath))

    def parse(self):
        threads = list()
        with self._filepath.open('r') as f:
            first_line = f.readline().rstrip('\n').split()
            if first_line[0] != MT_TAG:
                raise ValueError('Bad file')
            total_threads = int(first_line[1])
            for i in range(total_threads):
                #FIXME: FIlename may contain spaces....
                line_parts = f.readline().rstrip('\n').split()
                threads.append(self._parse_thread_line(i, line_parts))

        return threads

    def _parse_thread_line(self, thread_no, parts):
        args = [thread_no,]
        if parts[0] != T_TAG:
            raise ValueError('Thread tag not matching')

        filepath = self._filepath.parent / parts[1].replace('"', '')
        if not filepath.is_file():
            raise ValueError("File doesn't exist: " + str(filepath))

        for arg in parts[2:]:
            args.append(int(arg))

        return ThreadInfo(self._program_id, thread_no, str(filepath), args)
