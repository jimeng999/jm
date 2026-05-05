"""
数据分析 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List

from utils.auth import get_current_user
from utils.logger import logger
from services.prompt_templates import prompt_templates
from services.provider.base import Message
from services.provider.openai import openai_provider
from services.billing import billing_service
from config import plan_config


router = APIRouter(prefix="/v1/data", tags=["数据分析"])


# ==================== 请求/响应模型 ====================

class DataAnalyzeRequest(BaseModel):
    """数据分析请求"""
    data: str = Field(..., description="数据内容（CSV 格式或表格格式）")
    analysis_type: str = Field(
        default="trend",
        description="分析类型: trend, comparison, distribution, correlation, full_report"
    )
    report_format: str = Field(
        default="standard",
        description="报告格式: simple, standard, detailed"
    )
    title: Optional[str] = Field(default=None, description="报告标题")
    extra_requirements: Optional[str] = Field(default=None, description="额外需求")


class ChartDescription(BaseModel):
    """图表描述"""
    type: str = Field(description="图表类型: bar, line, pie, scatter, histogram")
    title: str = Field(description="图表标题")
    description: str = Field(description="图表描述/解读")


class DataInsight(BaseModel):
    """数据洞察"""
    category: str = Field(description="洞察类别")
    title: str = Field(description="洞察标题")
    description: str = Field(description="洞察描述")
    data_points: Optional[List[str]] = Field(default=None, description="支撑数据点")


class DataAnalyzeResponse(BaseModel):
    """数据分析响应"""
    report_id: str
    title: str
    executive_summary: str
    sections: List[dict]
    charts: List[ChartDescription]
    insights: List[DataInsight]
    conclusions: List[str]
    recommendations: List[str]
    model: str
    price: float
    remaining_balance: float


# ==================== 路由实现 ====================

@router.post("/analyze", response_model=DataAnalyzeResponse)
async def analyze_data(
    request: DataAnalyzeRequest,
    user: dict = Depends(get_current_user)
):
    """
    AI 数据分析接口
    
    支持多种分析类型：
    - trend: 趋势分析
    - comparison: 对比分析
    - distribution: 分布分析
    - correlation: 相关性分析
    - full_report: 完整报告
    
    按报告深度收费。
    """
    try:
        # 检查套餐是否包含此功能
        plan_info = plan_config.PLANS.get(user.get("plan", "free"), {})
        features = plan_info.get("features", [])
        
        if "data_analyze" not in features and "all" not in features:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前套餐不支持数据分析功能，请升级到专业版或企业版"
            )
        
        # 检查每日限制
        limit_check = billing_service.check_daily_limit(user)
        if not limit_check["allowed"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"每日请求次数已达上限 ({limit_check['message']})"
            )
        
        # 增加请求计数
        user_manager = __import__('models.user', fromlist=['user_manager']).user_manager
        user_manager.increment_request_count(user["user_id"])
        
        # 计算价格
        price = billing_service.get_vertical_api_price("data/analyze", request.report_format)
        
        # 检查余额
        if not billing_service.check_balance(user, price):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"余额不足，当前余额: {user.get('balance', 0):.2f} 元，需要: {price:.2f} 元"
            )
        
        # 生成提示词
        system_prompt = prompt_templates.DATA_ANALYSIS_SYSTEM
        
        user_prompt = prompt_templates.get_data_analysis_prompt(
            data=request.data,
            analysis_type=request.analysis_type
        )
        
        if request.extra_requirements:
            user_prompt += f"\n\n额外要求: {request.extra_requirements}"
        
        # 构造消息
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt)
        ]
        
        # 选择适合分析任务的模型
        model = "claude-3-5-sonnet-20241022"
        
        logger.info(f"Data analysis - User: {user['user_id']}, Type: {request.analysis_type}, Format: {request.report_format}")
        
        # 调用模型
        response = await openai_provider.chat_completion(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=_get_max_tokens(request.report_format)
        )
        
        # 提取分析结果
        content = response.choices[0].get("message", {}).get("content", "")
        
        # 解析报告
        report = _parse_analysis_report(
            content, 
            request.title or f"数据分析报告",
            request.report_format
        )
        
        # 扣费
        user_manager.deduct_balance(user["user_id"], price)
        
        # 记录用量
        usage_manager = __import__('models.usage', fromlist=['usage_manager']).usage_manager
        usage_manager.record_usage(
            user_id=user["user_id"],
            endpoint="/v1/data/analyze",
            model=model,
            input_tokens=response.usage.get("prompt_tokens", 0),
            output_tokens=response.usage.get("completion_tokens", 0),
            cost=0,
            revenue=price,
            metadata={"analysis_type": request.analysis_type, "format": request.report_format}
        )
        
        # 获取更新后的余额
        updated_user = user_manager.get_user(user["user_id"])
        
        import secrets
        return DataAnalyzeResponse(
            report_id=f"report_{secrets.token_hex(8)}",
            title=report.get("title", "数据分析报告"),
            executive_summary=report.get("summary", ""),
            sections=report.get("sections", []),
            charts=[ChartDescription(**c) for c in report.get("charts", [])],
            insights=[DataInsight(**i) for i in report.get("insights", [])],
            conclusions=report.get("conclusions", []),
            recommendations=report.get("recommendations", []),
            model=model,
            price=price,
            remaining_balance=updated_user.balance if updated_user else 0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Data analysis error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"数据分析失败: {str(e)}"
        )


def _get_max_tokens(format: str) -> int:
    """根据报告格式获取最大 token 数"""
    mapping = {
        "simple": 4000,
        "standard": 8000,
        "detailed": 16000
    }
    return mapping.get(format, 8000)


def _parse_analysis_report(content: str, title: str, format: str) -> dict:
    """解析分析报告"""
    # 简单的报告解析，实际项目中使用更复杂的解析逻辑
    sections = []
    charts = []
    insights = []
    conclusions = []
    recommendations = []
    
    lines = content.split("\n")
    
    # 提取摘要
    summary = ""
    for line in lines[:5]:
        if len(line.strip()) > 50:  # 较长的行可能是摘要
            summary = line.strip()
            break
    
    # 按章节解析
    current_section = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 检测标题
        if line.startswith("#") or (line.isupper() and len(line) > 5):
            if current_section:
                sections.append(current_section)
            current_section = {
                "title": line.strip("# ").strip(),
                "content": ""
            }
        elif current_section:
            current_section["content"] += line + "\n"
        
        # 检测图表
        if any(kw in line for kw in ["图", "图表", "Chart", "chart"]):
            charts.append({
                "type": "bar",
                "title": line[:50],
                "description": line
            })
        
        # 检测洞察
        if any(kw in line for kw in ["发现", "洞察", "Insight", "发现"]):
            insights.append({
                "category": "general",
                "title": line[:50],
                "description": line
            })
        
        # 检测结论
        if any(kw in line for kw in ["结论", "Conclusion", "综上"]):
            conclusions.append(line)
        
        # 检测建议
        if any(kw in line for kw in ["建议", "建议", "Recommend", "建议"]):
            recommendations.append(line)
    
    if current_section:
        sections.append(current_section)
    
    # 生成默认摘要
    if not summary:
        summary = f"本报告基于提供的数据进行了{format}级别的分析，生成了{len(sections)}个主要章节，发现了{len(insights)}个关键洞察。"
    
    return {
        "title": title,
        "summary": summary,
        "sections": sections[:10],  # 限制章节数
        "charts": charts[:5],
        "insights": insights[:5],
        "conclusions": conclusions[:5],
        "recommendations": recommendations[:5]
    }


@router.get("/analysis-types")
async def list_analysis_types(user: dict = Depends(get_current_user)):
    """列出支持的分析类型"""
    return {
        "types": [
            {
                "id": "trend",
                "name": "趋势分析",
                "description": "分析数据随时间变化的趋势",
                "suitable_for": "销售数据、用户增长、流量变化等"
            },
            {
                "id": "comparison",
                "name": "对比分析",
                "description": "对比不同组别或时间段的数据",
                "suitable_for": "A/B测试、产品对比、时间段对比等"
            },
            {
                "id": "distribution",
                "name": "分布分析",
                "description": "分析数据的分布形态和特征",
                "suitable_for": "用户画像、收入分布、评分分布等"
            },
            {
                "id": "correlation",
                "name": "相关性分析",
                "description": "分析变量之间的相关关系",
                "suitable_for": "影响因素分析、预测建模等"
            },
            {
                "id": "full_report",
                "name": "完整报告",
                "description": "综合所有分析维度生成完整报告",
                "suitable_for": "商业报告、决策支持等"
            }
        ],
        "pricing": {
            "simple": 30.0,
            "standard": 80.0,
            "detailed": 150.0
        }
    }
