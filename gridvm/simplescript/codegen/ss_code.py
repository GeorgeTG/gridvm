"""
Simple Script bytecode obejct file representation
"""

import pickle

from .ss_exception import CodeObjectException

MAGIC = 0xDA55C0DE

class SimpleScriptCodeObject(object):
    def __init__(self, instructions, consts, vars, arrays, labels, label_names):
        self.instructions = instructions
        self.co_vars = vars
        self.co_consts = consts
        self.co_arrays = arrays
        self.co_labels = labels
        self.co_label_names = label_names

    def to_bytes(self):
        code = (self.instructions,
                self.co_consts,
                self.co_vars,
                self.co_arrays,
                self.co_labels,
                self.co_label_names)
        return MAGIC.to_bytes(4, byteorder='big') + pickle.dumps(code, pickle.HIGHEST_PROTOCOL)

    @classmethod
    def from_bytes(cls, buff):
        magic = buff[:4]
        if MAGIC != int.from_bytes(magic, byteorder='big'):
            raise ValueError('Invalid SimpleScript code object')
        try:
            args = pickle.loads(buff[4:])
        except Exception as ex:
            raise CodeObjectException(ex)

        return cls(*args)

    def to_file(self, filename):
        with open(filename, 'wb') as f:
            f.write(MAGIC.to_bytes(4, byteorder='big'))
            code = (self.instructions,
                self.co_consts,
                self.co_vars,
                self.co_arrays,
                self.co_labels,
                self.co_label_names)

            pickle.dump(code, f, pickle.HIGHEST_PROTOCOL)

    @classmethod
    def from_file(cls, filename):
        with open(filename, 'rb') as f:
            magic = f.read(4)
            if MAGIC != int.from_bytes(magic, byteorder='big'):
                raise ValueError('Invalid SimpleScript code object file')
            try:
                args = pickle.load(f)
            except Exception as ex:
                raise CodeObjectException(ex)

            return cls(*args)


