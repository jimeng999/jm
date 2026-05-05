"""
加密工具 - 用于加密存储用户 API Keys
"""
import base64
import hashlib
import os
from cryptography.fernet import Fernet
from config import settings


class KeyEncryptor:
    """API Key 加密器"""
    
    def __init__(self):
        # 使用 JWT_SECRET_KEY 作为加密密钥
        key = hashlib.sha256(settings.jwt_secret_key.encode()).digest()
        self._cipher = Fernet(base64.urlsafe_b64encode(key))
    
    def encrypt(self, plaintext: str) -> str:
        """加密字符串"""
        if not plaintext:
            return ""
        encrypted = self._cipher.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """解密字符串"""
        if not ciphertext:
            return ""
        try:
            decoded = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self._cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception:
            return ""


# 全局加密器实例
key_encryptor = KeyEncryptor()


def mask_api_key(key: str, visible_chars: int = 4) -> str:
    """脱敏显示 API Key"""
    if not key:
        return ""
    if len(key) <= visible_chars * 2:
        return key[:visible_chars] + "***"
    return key[:visible_chars] + "***" + key[-visible_chars:]
