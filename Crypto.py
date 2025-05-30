import hashlib
import os
from Crypto.Cipher import AES

class Crypto:
    def __init__(self, passphrase):
        # Crear clave sha256 de 32 bytes
        self.key = hashlib.sha256(passphrase.encode('utf-8')).digest()
        self.block_size = AES.block_size  # normalmente 16 bytes

    def pad(self, data):
        pad_len = self.block_size - (len(data) % self.block_size)
        return data + bytes([pad_len] * pad_len)

    def unpad(self, data):
        pad_len = data[-1]
        return data[:-pad_len]

    def encrypt(self, plaintext):
        # plaintext es str → convertir a bytes
        data = plaintext.encode('utf-8')
        padded = self.pad(data)
        iv = os.urandom(self.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(padded)
        return iv + encrypted  # IV + mensaje cifrado

    def decrypt(self, encrypted):
        # encrypted es bytes → separar IV y ciphertext
        iv = encrypted[:self.block_size]
        ciphertext = encrypted[self.block_size:]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        padded = cipher.decrypt(ciphertext)
        data = self.unpad(padded)
        return data.decode('utf-8')