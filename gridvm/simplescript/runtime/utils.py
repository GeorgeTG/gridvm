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



