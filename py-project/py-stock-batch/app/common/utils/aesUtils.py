from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import base64

class AesUtils:
    def __init__(self):
        self.__iv = (b"\x00" * 16)
        self.BLOCK_SIZE = AES.block_size
        self.UTF8 = 'utf-8'
        with open('./aes.key') as aesf:
            lines = aesf.readlines()
            self.key = lines[0].strip().encode('utf-8')

    def encrypt(self, plain):
        cipher = AES.new(self.key, AES.MODE_CBC, self.__iv)  # CBC 모드
        ct_bytes = cipher.encrypt(pad(plain.encode(), self.BLOCK_SIZE))
        return base64.b64encode(ct_bytes).decode(self.UTF8)  # 암호문도 base64로 인코딩
    
    def decrypt(self, encrypted):
        cipher = AES.new(self.key, AES.MODE_CBC, self.__iv)
        return unpad(cipher.decrypt(base64.b64decode(encrypted)), self.BLOCK_SIZE).decode(self.UTF8)
    
aesUtils = AesUtils()