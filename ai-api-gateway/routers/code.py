"""
代码审查 API 路由
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


router = APIRouter(prefix="/v1/code", tags=["代码审查"])


# ==================== 请求/响应模型 ====================

class CodeReviewRequest(BaseModel):
    """代码审查请求"""
    code: str = Field(..., description="需要审查的代码")
    language: str = Field(default="python", description="编程语言")
    focus_areas: List[str] = Field(
        default=["basic"],
        description="审查重点: basic, security, performance, best_practice, full"
    )
    tier: str = Field(default="standard", description="审查深度: basic, standard, detailed")


class CodeIssue(BaseModel):
    """代码问题"""
    severity: str = Field(description="严重程度: critical, high, medium, low, info")
    line: Optional[int] = Field(default=None, description="问题所在行")
    type: str = Field(description="问题类型")
    description: str = Field(description="问题描述")
    suggestion: str = Field(description="修改建议")
    code: Optional[str] = Field(default=None, description="建议的修改代码")


class CodeReviewResponse(BaseModel):
    """代码审查响应"""
    review_id: str
    summary: str
    score: int = Field(ge=0, le=100, description="代码评分 0-100")
    issues: List[CodeIssue]
    strengths: List[str]
    suggestions: List[str]
    model: str
    price: float
    remaining_balance: float


# ==================== 路由实现 ====================

@router.post("/review", response_model=CodeReviewResponse)
async def review_code(
    request: CodeReviewRequest,
    user: dict = Depends(get_current_user)
):
    """
    AI 代码审查接口
    
    支持多种审查类型：
    - basic: 基础代码质量审查
    - security: 安全审查
    - performance: 性能审查
    - full: 全面审查
    
    按审查深度收费。
    """
    try:
        # 检查套餐是否包含此功能
        plan_info = plan_config.PLANS.get(user.get("plan", "free"), {})
        features = plan_info.get("features", [])
        
        if "code_review" not in features and "all" not in features:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="当前套餐不支持代码审查功能，请升级到专业版或企业版"
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
        price = billing_service.get_vertical_api_price("code/review", request.tier)
        
        # 检查余额
        if not billing_service.check_balance(user, price):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"余额不足，当前余额: {user.get('balance', 0):.2f} 元，需要: {price:.2f} 元"
            )
        
        # 生成提示词
        system_prompt = prompt_templates.CODE_REVIEW_SYSTEM
        
        user_prompt = prompt_templates.get_code_review_prompt(
            code=request.code,
            language=request.language,
            focus_areas=request.focus_areas,
            model=request.tier
        )
        
        # 构造消息
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt)
        ]
        
        # 选择适合代码任务的模型（Claude 擅长代码）
        model = "claude-3-5-sonnet-20241022"  # 使用 Claude 进行代码审查
        
        logger.info(f"Code review - User: {user['user_id']}, Language: {request.language}, Tier: {request.tier}")
        
        # 调用模型
        response = await openai_provider.chat_completion(
            model=model,
            messages=messages,
            temperature=0.3,  # 代码审查需要较低的温度
            max_tokens=8000
        )
        
        # 提取审查结果
        content = response.choices[0].get("message", {}).get("content", "")
        
        # 解析审查结果
        review_result = _parse_review_result(content)
        
        # 扣费
        user_manager.deduct_balance(user["user_id"], price)
        
        # 记录用量
        usage_manager = __import__('models.usage', fromlist=['usage_manager']).usage_manager
        usage_manager.record_usage(
            user_id=user["user_id"],
            endpoint="/v1/code/review",
            model=model,
            input_tokens=response.usage.get("prompt_tokens", 0),
            output_tokens=response.usage.get("completion_tokens", 0),
            cost=0,
            revenue=price,
            metadata={"language": request.language, "issues_count": len(review_result.get("issues", []))}
        )
        
        # 获取更新后的余额
        updated_user = user_manager.get_user(user["user_id"])
        
        import secrets
        return CodeReviewResponse(
            review_id=f"review_{secrets.token_hex(8)}",
            summary=review_result.get("summary", ""),
            score=review_result.get("score", 80),
            issues=[CodeIssue(**issue) for issue in review_result.get("issues", [])],
            strengths=review_result.get("strengths", []),
            suggestions=review_result.get("suggestions", []),
            model=model,
            price=price,
            remaining_balance=updated_user.balance if updated_user else 0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Code review error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"代码审查失败: {str(e)}"
        )


def _parse_review_result(content: str) -> dict:
    """解析审查结果（简单实现）"""
    # 简单解析，实际项目中可以使用更复杂的解析逻辑
    lines = content.split("\n")
    
    issues = []
    strengths = []
    suggestions = []
    summary = ""
    score = 85  # 默认分数
    
    # 提取摘要
    for i, line in enumerate(lines):
        if "评分" in line or "Score" in line:
            # 尝试提取分数
            import re
            match = re.search(r'\d+', line)
            if match:
                score = int(match.group())
        
        # 简单识别问题
        if any(kw in line.lower() for kw in ["问题", "issue", "bug", "error", "warning"]):
            issues.append({
                "severity": "medium",
                "type": "general",
                "description": line.strip(),
                "suggestion": "请检查并修复上述问题"
            })
    
    # 提取优点
    if "优点" in content or "Strengths" in content:
        for line in lines:
            if "✓" in line or "优点" in line:
                strengths.append(line.strip())
    
    # 提取建议
    if "建议" in content or "suggestion" in content.lower():
        for line in lines:
            if "建议" in line:
                suggestions.append(line.strip())
    
    if not summary:
        summary = f"代码审查完成，发现 {len(issues)} 个问题，建议 {len(suggestions)} 项改进。"
    
    return {
        "summary": summary,
        "score": score,
        "issues": issues[:10],  # 限制最多 10 个问题
        "strengths": strengths[:5],
        "suggestions": suggestions[:5]
    }


@router.get("/languages")
async def list_supported_languages(user: dict = Depends(get_current_user)):
    """列出支持的编程语言"""
    return {
        "languages": [
            "python", "javascript", "typescript", "java", "go", "rust",
            "cpp", "c", "csharp", "ruby", "php", "swift", "kotlin",
            "scala", "sql", "html", "css", "shell", "powershell"
        ],
        "pricing": {
            "basic": 3.0,
            "standard": 8.0,
            "detailed": 15.0
        }
    }
