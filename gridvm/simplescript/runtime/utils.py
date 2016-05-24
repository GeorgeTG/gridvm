import hashlib
import base64

def fast_hash(buff, length=8):
    try:
        buff = buff.encode('utf-8')
    except:
        pass

    h = hashlib.sha256(buff)
    h = h.digest()
    return str(base64.urlsafe_b64encode(h), 'ascii')[:length]


def get_thread_uid(program_id, thread_id):
    return fast_hash(str(program_id) + str(thread_id))
