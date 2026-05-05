"""
SimpleStore - 轻量级内存存储 (兼容 Vercel Serverless)
用于存储用户 BYOK Keys 和其他临时数据
"""
import json
import threading
from typing import Any, Dict, Optional
from datetime import datetime, timedelta


class SimpleStore:
    """简单的线程安全内存存储"""
    
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._lock = threading.RLock()
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """设置值，ttl 单位秒"""
        with self._lock:
            self._store[key] = {
                "value": value,
                "expires_at": (datetime.now() + timedelta(seconds=ttl)).isoformat() if ttl else None
            }
            return True
    
    def get(self, key: str) -> Optional[Any]:
        """获取值，自动清理过期数据"""
        with self._lock:
            if key not in self._store:
                return None
            
            item = self._store[key]
            # 检查过期
            if item.get("expires_at"):
                expires = datetime.fromisoformat(item["expires_at"])
                if datetime.now() > expires:
                    del self._store[key]
                    return None
            
            return item.get("value")
    
    def delete(self, key: str) -> bool:
        """删除值"""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有非过期数据"""
        with self._lock:
            result = {}
            now = datetime.now()
            expired_keys = []
            
            for key, item in self._store.items():
                if item.get("expires_at"):
                    expires = datetime.fromisoformat(item["expires_at"])
                    if now > expires:
                        expired_keys.append(key)
                        continue
                result[key] = item.get("value")
            
            # 清理过期数据
            for key in expired_keys:
                del self._store[key]
            
            return result
    
    def clear(self) -> bool:
        """清空所有数据"""
        with self._lock:
            self._store.clear()
            return True


# 全局存储实例
store = SimpleStore()


# ==================== 快捷方法 ====================

def set_user_byok_key(user_id: str, provider: str, api_key: str) -> bool:
    """存储用户的 BYOK Key"""
    return store.set(f"byok:{user_id}:{provider}", api_key)


def get_user_byok_key(user_id: str, provider: str) -> Optional[str]:
    """获取用户的 BYOK Key"""
    return store.get(f"byok:{user_id}:{provider}")


def delete_user_byok_key(user_id: str, provider: str) -> bool:
    """删除用户的 BYOK Key"""
    return store.delete(f"byok:{user_id}:{provider}")


def get_user_all_byok_keys(user_id: str) -> Dict[str, str]:
    """获取用户所有 BYOK Keys"""
    all_keys = store.get_all()
    return {
        k.split(":")[-1]: v 
        for k, v in all_keys.items() 
        if k.startswith(f"byok:{user_id}:")
    }


# ==================== 免费体验计数 ====================

def get_free_trial_count(user_id: str) -> int:
    """获取用户今日免费体验次数"""
    return store.get(f"free_trial:{user_id}") or 0


def increment_free_trial(user_id: str) -> int:
    """增加免费体验计数（每天重置）"""
    count = get_free_trial_count(user_id)
    count += 1
    # 设置24小时过期
    store.set(f"free_trial:{user_id}", count, ttl=86400)
    return count


def reset_free_trial(user_id: str) -> bool:
    """重置免费体验计数"""
    return store.delete(f"free_trial:{user_id}")
