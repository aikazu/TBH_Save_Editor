"""
Pure-Python AES-128 (no dependencies) + CBC. Used as a fallback when the
'cryptography' library (or pycryptodome) is not installed. Tables generated via
GF(2^8) (avoids S-box typos). Validated against the NIST FIPS-197 test vector.
"""

def _gen_sbox():
    sbox = [0] * 256
    p = q = 1
    while True:
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
        p &= 0xFF
        q ^= (q << 1) & 0xFF
        q ^= (q << 2) & 0xFF
        q ^= (q << 4) & 0xFF
        if q & 0x80:
            q ^= 0x09
        q &= 0xFF
        xf = q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) ^ ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4))
        sbox[p] = (xf ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    return sbox


_SBOX = _gen_sbox()
_INV_SBOX = [0] * 256
for _i, _v in enumerate(_SBOX):
    _INV_SBOX[_v] = _i
_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36, 0x6C, 0xD8, 0xAB, 0x4D]


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a ^= 0x11B
    return a & 0xFF


def _mul(a, b):
    r = 0
    for _ in range(8):
        if b & 1:
            r ^= a
        b >>= 1
        a = _xtime(a)
    return r


def _key_expansion(key):
    # AES-128: 16-byte key -> 11 round keys (44 words)
    Nk, Nr = 4, 10
    w = [list(key[4 * i:4 * i + 4]) for i in range(Nk)]
    for i in range(Nk, 4 * (Nr + 1)):
        temp = list(w[i - 1])
        if i % Nk == 0:
            temp = temp[1:] + temp[:1]                       # RotWord
            temp = [_SBOX[b] for b in temp]                  # SubWord
            temp[0] ^= _RCON[i // Nk - 1]
        w.append([w[i - Nk][j] ^ temp[j] for j in range(4)])
    # round keys as list of 16-byte states (column-major matches Unity/.NET AES)
    return [sum(w[r * 4:r * 4 + 4], []) for r in range(Nr + 1)]


def _add_round_key(s, rk):
    return [s[i] ^ rk[i] for i in range(16)]


def _sub_bytes(s, box):
    return [box[b] for b in s]


# state is treated as column-major: byte index = col*4 + row
def _shift_rows(s):
    o = [0] * 16
    for r in range(4):
        for c in range(4):
            o[c * 4 + r] = s[((c + r) % 4) * 4 + r]
    return o


def _inv_shift_rows(s):
    o = [0] * 16
    for r in range(4):
        for c in range(4):
            o[c * 4 + r] = s[((c - r) % 4) * 4 + r]
    return o


def _mix_columns(s):
    o = [0] * 16
    for c in range(4):
        col = s[c * 4:c * 4 + 4]
        o[c * 4 + 0] = _mul(col[0], 2) ^ _mul(col[1], 3) ^ col[2] ^ col[3]
        o[c * 4 + 1] = col[0] ^ _mul(col[1], 2) ^ _mul(col[2], 3) ^ col[3]
        o[c * 4 + 2] = col[0] ^ col[1] ^ _mul(col[2], 2) ^ _mul(col[3], 3)
        o[c * 4 + 3] = _mul(col[0], 3) ^ col[1] ^ col[2] ^ _mul(col[3], 2)
    return o


def _inv_mix_columns(s):
    o = [0] * 16
    for c in range(4):
        col = s[c * 4:c * 4 + 4]
        o[c * 4 + 0] = _mul(col[0], 14) ^ _mul(col[1], 11) ^ _mul(col[2], 13) ^ _mul(col[3], 9)
        o[c * 4 + 1] = _mul(col[0], 9) ^ _mul(col[1], 14) ^ _mul(col[2], 11) ^ _mul(col[3], 13)
        o[c * 4 + 2] = _mul(col[0], 13) ^ _mul(col[1], 9) ^ _mul(col[2], 14) ^ _mul(col[3], 11)
        o[c * 4 + 3] = _mul(col[0], 11) ^ _mul(col[1], 13) ^ _mul(col[2], 9) ^ _mul(col[3], 14)
    return o


def _encrypt_block(block, rks):
    s = _add_round_key(list(block), rks[0])
    for r in range(1, 10):
        s = _sub_bytes(s, _SBOX)
        s = _shift_rows(s)
        s = _mix_columns(s)
        s = _add_round_key(s, rks[r])
    s = _sub_bytes(s, _SBOX)
    s = _shift_rows(s)
    s = _add_round_key(s, rks[10])
    return bytes(s)


def _decrypt_block(block, rks):
    s = _add_round_key(list(block), rks[10])
    for r in range(9, 0, -1):
        s = _inv_shift_rows(s)
        s = _sub_bytes(s, _INV_SBOX)
        s = _add_round_key(s, rks[r])
        s = _inv_mix_columns(s)
    s = _inv_shift_rows(s)
    s = _sub_bytes(s, _INV_SBOX)
    s = _add_round_key(s, rks[0])
    return bytes(s)


def cbc_decrypt(key, iv, data):
    rks = _key_expansion(key)
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        block = data[i:i + 16]
        dec = _decrypt_block(block, rks)
        out += bytes(a ^ b for a, b in zip(dec, prev))
        prev = block
    return bytes(out)


def cbc_encrypt(key, iv, data):
    rks = _key_expansion(key)
    out = bytearray()
    prev = iv
    for i in range(0, len(data), 16):
        block = bytes(a ^ b for a, b in zip(data[i:i + 16], prev))
        enc = _encrypt_block(block, rks)
        out += enc
        prev = enc
    return bytes(out)
