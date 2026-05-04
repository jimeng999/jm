"""
用量模型与数据管理
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel
from collections import defaultdict

from config import settings


class UsageRecord(BaseModel):
    """用量记录模型"""
    usage_id: str
    user_id: str
    endpoint: str
    model: Optional[str]
    input_tokens: int
    output_tokens: int
    cost: float  # 成本（向供应商支付）
    revenue: float  # 收入（向用户收取）
    profit: float  # 利润
    created_at: str
    metadata: Dict = {}


class UsageManager:
    """用量数据管理器"""
    
    def __init__(self):
        self.data_file = settings.data_dir / "usage.json"
        self._init_storage()
    
    def _init_storage(self):
        """初始化存储"""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self._save_data({"records": [], "daily_stats": {}})
    
    def _load_data(self) -> dict:
        """加载数据"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"records": [], "daily_stats": {}}
    
    def _save_data(self, data: dict):
        """保存数据"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def record_usage(
        self,
        user_id: str,
        endpoint: str,
        model: Optional[str],
        input_tokens: int,
        output_tokens: int,
        cost: float,
        revenue: float,
        metadata: Dict = None
    ) -> UsageRecord:
        """记录用量"""
        data = self._load_data()
        
        import secrets
        usage_id = f"usage_{secrets.token_hex(16)}"
        now = datetime.now().isoformat()
        
        record = UsageRecord(
            usage_id=usage_id,
            user_id=user_id,
            endpoint=endpoint,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            revenue=revenue,
            profit=revenue - cost,
            created_at=now,
            metadata=metadata or {}
        )
        
        data["records"].append(record.to_dict())
        
        # 更新每日统计
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in data["daily_stats"]:
            data["daily_stats"][today] = {
                "total_requests": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cost": 0,
                "total_revenue": 0,
                "profit": 0
            }
        
        stats = data["daily_stats"][today]
        stats["total_requests"] += 1
        stats["total_input_tokens"] += input_tokens
        stats["total_output_tokens"] += output_tokens
        stats["total_cost"] += cost
        stats["total_revenue"] += revenue
        stats["profit"] += (revenue - cost)
        
        # 限制记录数量，只保留最近 10000 条
        if len(data["records"]) > 10000:
            data["records"] = data["records"][-10000:]
        
        self._save_data(data)
        return record
    
    def get_user_usage(
        self,
        user_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[UsageRecord]:
        """获取用户用量记录"""
        data = self._load_data()
        records = []
        
        for record in reversed(data.get("records", [])):
            if record.get("user_id") == user_id:
                if start_date and record["created_at"] < start_date:
                    continue
                if end_date and record["created_at"] > end_date:
                    continue
                records.append(UsageRecord(**record))
                if len(records) >= limit:
                    break
        
        return records
    
    def get_user_stats(self, user_id: str) -> Dict:
        """获取用户用量统计"""
        data = self._load_data()
        
        total_input = 0
        total_output = 0
        total_cost = 0
        total_revenue = 0
        total_requests = 0
        
        endpoint_stats = defaultdict(lambda: {"count": 0, "tokens": 0, "cost": 0})
        model_stats = defaultdict(lambda: {"count": 0, "tokens": 0, "cost": 0})
        
        for record in data.get("records", []):
            if record.get("user_id") == user_id:
                total_requests += 1
                total_input += record.get("input_tokens", 0)
                total_output += record.get("output_tokens", 0)
                total_cost += record.get("cost", 0)
                total_revenue += record.get("revenue", 0)
                
                endpoint = record.get("endpoint", "unknown")
                endpoint_stats[endpoint]["count"] += 1
                endpoint_stats[endpoint]["tokens"] += record.get("input_tokens", 0) + record.get("output_tokens", 0)
                endpoint_stats[endpoint]["cost"] += record.get("revenue", 0)
                
                model = record.get("model", "unknown")
                if model:
                    model_stats[model]["count"] += 1
                    model_stats[model]["tokens"] += record.get("input_tokens", 0) + record.get("output_tokens", 0)
                    model_stats[model]["cost"] += record.get("revenue", 0)
        
        return {
            "total_requests": total_requests,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost": total_cost,
            "total_revenue": total_revenue,
            "profit": total_revenue - total_cost,
            "endpoint_stats": dict(endpoint_stats),
            "model_stats": dict(model_stats)
        }
    
    def get_daily_stats(self, days: int = 30) -> List[Dict]:
        """获取每日统计"""
        data = self._load_data()
        stats = []
        
        for i in range(days):
            date = (datetime.now().replace(hour=0, minute=0, second=0) - 
                   datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            
            if date in data.get("daily_stats", {}):
                stats.append({
                    "date": date,
                    **data["daily_stats"][date]
                })
            else:
                stats.append({
                    "date": date,
                    "total_requests": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cost": 0,
                    "total_revenue": 0,
                    "profit": 0
                })
        
        return stats
    
    def get_overall_stats(self) -> Dict:
        """获取整体统计"""
        data = self._load_data()
        
        total_cost = 0
        total_revenue = 0
        total_requests = 0
        total_input = 0
        total_output = 0
        
        for record in data.get("records", []):
            total_requests += 1
            total_input += record.get("input_tokens", 0)
            total_output += record.get("output_tokens", 0)
            total_cost += record.get("cost", 0)
            total_revenue += record.get("revenue", 0)
        
        return {
            "total_requests": total_requests,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost": total_cost,
            "total_revenue": total_revenue,
            "profit": total_revenue - total_cost,
            "profit_margin": ((total_revenue - total_cost) / total_revenue * 100) if total_revenue > 0 else 0
        }


# 全局用量管理器
usage_manager = UsageManager()
