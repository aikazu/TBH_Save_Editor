"""
Save layer: decrypts/encrypts the SaveFile .es3 (Easy Save 3, AES-128-CBC),
un-nests the inner JSON (Account/Player) and recomputes the SystemInfo (integrity
HMAC) on save. Zero mandatory dependencies (uses 'cryptography' if available,
otherwise the built-in pure AES).
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
from hashlib import pbkdf2_hmac

# --- keys/constants (Taskbar Hero 1.00.17) ---
ES3_PASSWORD = "emuMqG3bLYJ938ZDCfieWJ"          # Easy Save 3 encryption password
PBKDF2_ITERS = 100
KEY_SIZE = 16
IV_SIZE = 16
# HMAC-SHA256 integrity key ("SystemInfo" field); extracted at runtime and validated.
SYSTEMINFO_HMAC_KEY = bytes.fromhex(
    "93d9429e9b72f22fdb3413193763eaba1e8cfae995f61466a81a36a609d8e456"
)
SYSTEMINFO_SEP = "|"

# --- AES-CBC: uses 'cryptography' (fast) if available, otherwise pure AES ---
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    def _aes_cbc_decrypt(key, iv, data):
        d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return d.update(data) + d.finalize()

    def _aes_cbc_encrypt(key, iv, data):
        e = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        return e.update(data) + e.finalize()

    AES_BACKEND = "cryptography"
except Exception:
    from . import aes_pure

    def _aes_cbc_decrypt(key, iv, data):
        return aes_pure.cbc_decrypt(key, iv, data)

    def _aes_cbc_encrypt(key, iv, data):
        return aes_pure.cbc_encrypt(key, iv, data)

    AES_BACKEND = "pure-python"


def _pkcs7_pad(data, block=16):
    n = block - (len(data) % block)
    return data + bytes([n]) * n


def _pkcs7_unpad(data):
    n = data[-1]
    if n < 1 or n > 16:
        raise ValueError("invalid PKCS7 padding")
    return data[:-n]


def _derive_key(password, iv):
    return pbkdf2_hmac("sha1", password.encode("utf-8"), iv, PBKDF2_ITERS, dklen=KEY_SIZE)


def es3_decrypt(raw, password=ES3_PASSWORD):
    iv, ct = raw[:IV_SIZE], raw[IV_SIZE:]
    key = _derive_key(password, iv)
    return _pkcs7_unpad(_aes_cbc_decrypt(key, iv, ct))


def es3_encrypt(plaintext, password=ES3_PASSWORD, iv=None):
    if iv is None:
        iv = secrets.token_bytes(IV_SIZE)
    key = _derive_key(password, iv)
    return iv + _aes_cbc_encrypt(key, iv, _pkcs7_pad(plaintext))


class SaveFile:
    """Loaded and un-nested save. `account` and `player` are editable dicts."""

    def __init__(self, es3_obj, password=ES3_PASSWORD):
        self._es3 = es3_obj           # outer ES3 structure {key: {__type, value}}
        self.password = password
        self.account = json.loads(es3_obj["AccountSaveData"]["value"])
        self.player = json.loads(es3_obj["PlayerSaveData"]["value"])

    @classmethod
    def load(cls, path, password=ES3_PASSWORD):
        with open(path, "rb") as fh:
            raw = fh.read()
        es3_obj = json.loads(es3_decrypt(raw, password).decode("utf-8"))
        return cls(es3_obj, password)

    def _serialize_inner(self, obj):
        # compact, raw UTF-8 -- matches Newtonsoft (semantically equivalent)
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

    def to_es3_bytes(self):
        acc = self._serialize_inner(self.account)
        ply = self._serialize_inner(self.player)
        steam = str(self.account.get("ownerSteamId", ""))
        msg = SYSTEMINFO_SEP.join([acc, ply, steam]).encode("utf-8")
        sysinfo = base64.b64encode(
            hmac.new(SYSTEMINFO_HMAC_KEY, msg, hashlib.sha256).digest()
        ).decode("ascii")
        self._es3["AccountSaveData"]["value"] = acc
        self._es3["PlayerSaveData"]["value"] = ply
        self._es3["SystemInfo"]["value"] = sysinfo
        text = json.dumps(self._es3, ensure_ascii=False, indent="\t")
        return es3_encrypt(text.encode("utf-8"), self.password)

    def save(self, path, backup=True):
        blob = self.to_es3_bytes()
        if backup and os.path.exists(path):
            with open(path, "rb") as s, open(path + ".bak", "wb") as d:
                d.write(s.read())
        with open(path, "wb") as fh:
            fh.write(blob)
        return path
