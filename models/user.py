"""
用户模型与数据管理
"""
import json
import aiofiles
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from config import settings
from utils.auth import generate_api_key, generate_user_id, hash_password, verify_password


class User(BaseModel):
    """用户模型"""
    user_id: str
    email: str
    password_hash: str
    plan: str = "free"
    api_key: str
    balance: float = 0.0
    created_at: str
    updated_at: str
    is_active: bool = True
    daily_requests: int = 0
    last_request_date: Optional[str] = None
    total_requests: int = 0
    
    def to_dict(self) -> dict:
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(**data)


class UserManager:
    """用户数据管理器"""
    
    def __init__(self):
        self.data_file = settings.data_dir / "users.json"
        self._init_storage()
    
    def _init_storage(self):
        """初始化存储"""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self._save_data({})
    
    def _load_data(self) -> dict:
        """加载数据"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _save_data(self, data: dict):
        """保存数据"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _get_date_key(self) -> str:
        """获取当前日期键"""
        return datetime.now().strftime("%Y-%m-%d")
    
    def create_user(self, email: str, password: str) -> Optional[User]:
        """创建用户"""
        data = self._load_data()
        
        # 检查邮箱是否已存在
        for user_data in data.values():
            if user_data.get("email") == email:
                return None
        
        now = datetime.now().isoformat()
        user_id = generate_user_id()
        api_key = generate_api_key()
        
        user = User(
            user_id=user_id,
            email=email,
            password_hash=hash_password(password),
            plan="free",
            api_key=api_key,
            balance=0.0,
            created_at=now,
            updated_at=now,
            is_active=True,
            daily_requests=0,
            total_requests=0
        )
        
        data[user_id] = user.to_dict()
        self._save_data(data)
        
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
        data = self._load_data()
        user_data = data.get(user_id)
        if user_data:
            # 检查日期并重置每日请求数
            today = self._get_date_key()
            if user_data.get("last_request_date") != today:
                user_data["daily_requests"] = 0
                user_data["last_request_date"] = today
            return User.from_dict(user_data)
        return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        data = self._load_data()
        for user_data in data.values():
            if user_data.get("email") == email:
                return User.from_dict(user_data)
        return None
    
    def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """通过 API Key 获取用户"""
        data = self._load_data()
        for user_data in data.values():
            if user_data.get("api_key") == api_key and user_data.get("is_active"):
                today = self._get_date_key()
                if user_data.get("last_request_date") != today:
                    user_data["daily_requests"] = 0
                    user_data["last_request_date"] = today
                return User.from_dict(user_data)
        return None
    
    def authenticate(self, email: str, password: str) -> Optional[User]:
        """验证用户登录"""
        user = self.get_user_by_email(email)
        if user and verify_password(password, user.password_hash) and user.is_active:
            return user
        return None
    
    def update_user(self, user_id: str, updates: dict) -> Optional[User]:
        """更新用户信息"""
        data = self._load_data()
        if user_id not in data:
            return None
        
        updates["updated_at"] = datetime.now().isoformat()
        data[user_id].update(updates)
        self._save_data(data)
        
        return User.from_dict(data[user_id])
    
    def increment_request_count(self, user_id: str) -> bool:
        """增加请求计数"""
        data = self._load_data()
        if user_id not in data:
            return False
        
        today = self._get_date_key()
        if data[user_id].get("last_request_date") != today:
            data[user_id]["daily_requests"] = 0
            data[user_id]["last_request_date"] = today
        
        data[user_id]["daily_requests"] += 1
        data[user_id]["total_requests"] += 1
        data[user_id]["updated_at"] = datetime.now().isoformat()
        
        self._save_data(data)
        return True
    
    def add_balance(self, user_id: str, amount: float) -> Optional[User]:
        """增加余额"""
        data = self._load_data()
        if user_id not in data:
            return None
        
        data[user_id]["balance"] = data[user_id].get("balance", 0) + amount
        data[user_id]["updated_at"] = datetime.now().isoformat()
        
        self._save_data(data)
        return User.from_dict(data[user_id])
    
    def deduct_balance(self, user_id: str, amount: float) -> bool:
        """扣减余额"""
        data = self._load_data()
        if user_id not in data:
            return False
        
        current_balance = data[user_id].get("balance", 0)
        if current_balance < amount:
            return False
        
        data[user_id]["balance"] = current_balance - amount
        data[user_id]["updated_at"] = datetime.now().isoformat()
        
        self._save_data(data)
        return True
    
    def update_plan(self, user_id: str, plan: str) -> Optional[User]:
        """更新用户套餐"""
        return self.update_user(user_id, {"plan": plan})
    
    def list_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """列出用户"""
        data = self._load_data()
        users = list(data.values())[offset:offset+limit]
        return [User.from_dict(u) for u in users]
    
    def get_stats(self) -> dict:
        """获取用户统计"""
        data = self._load_data()
        total_users = len(data)
        active_users = sum(1 for u in data.values() if u.get("is_active"))
        total_requests = sum(u.get("total_requests", 0) for u in data.values())
        total_balance = sum(u.get("balance", 0) for u in data.values())
        
        plan_distribution = {}
        for u in data.values():
            plan = u.get("plan", "free")
            plan_distribution[plan] = plan_distribution.get(plan, 0) + 1
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_requests": total_requests,
            "total_balance": total_balance,
            "plan_distribution": plan_distribution
        }


# 全局用户管理器
user_manager = UserManager()
