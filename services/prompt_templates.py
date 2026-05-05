"""
提示词模板服务
"""
from typing import Dict, List, Optional


class PromptTemplates:
    """提示词模板库"""
    
    # ========== 内容创作模板 ==========
    
    CONTENT_WRITE_SYSTEM = """你是一位专业的内容创作者，擅长撰写各类文章、文案和营销内容。
请根据用户的要求，创作高质量、有价值的内容。

要求：
1. 内容要专业、有深度
2. 语言要流畅、易读
3. 结构要清晰、有逻辑
4. 根据指定的风格调整表达方式

直接输出内容，不要添加额外的解释。"""
    
    CONTENT_WRITE_TEMPLATES = {
        "article": {
            "short": """请撰写一篇关于"{topic}"的简短文章，要求：
- 字数：500-800字
- 结构：引言 + 2-3个要点 + 结论
- 风格：{style}

直接输出文章内容。""",
            "medium": """请撰写一篇关于"{topic}"的完整文章，要求：
- 字数：1000-1500字
- 结构：引言 + 4-6个要点 + 结论 + 行动建议
- 风格：{style}
- 可以包含小标题

直接输出文章内容。""",
            "long": """请撰写一篇关于"{topic}"的深度长文，要求：
- 字数：2500-4000字
- 结构：引言 + 多个章节 + 案例分析 + 结论
- 风格：{style}
- 需要有数据支撑或案例引用
- 包含实用的建议和指导

直接输出文章内容。"""
        },
        "seo": {
            "prompt": """请为"{keyword}"撰写一篇SEO优化的文章，要求：
- 自然融入关键词{keyword}
- 字数：1500-2000字
- 包含{count}个相关关键词
- 结构清晰，有小标题
- 结尾包含CTA

直接输出文章内容。"""
        },
        "marketing": {
            "prompt": """请为产品/服务"{product}"撰写营销文案，要求：
- 目标受众：{audience}
- 文案类型：{type}（产品介绍/朋友圈/广告语/销售话术）
- 风格：{style}（专业/亲切/紧迫/幽默）
- 突出卖点：{selling_points}

直接输出文案。"""
        }
    }
    
    # ========== 代码审查模板 ==========
    
    CODE_REVIEW_SYSTEM = """你是一位资深的代码审查专家，擅长发现代码中的问题并提供改进建议。
请对用户提供的代码进行全面审查，包括：
1. 代码质量和风格
2. 潜在 bug 和安全问题
3. 性能优化建议
4. 最佳实践建议
5. 代码可读性和可维护性

以结构化的方式输出审查结果。"""
    
    CODE_REVIEW_TEMPLATES = {
        "basic": {
            "prompt": """请审查以下{model}代码，重点关注基本质量问题：

```{language}
{code}
```

请简要列出发现的问题和改进建议。"""
        },
        "security": {
            "prompt": """请对以下代码进行安全审查：

```{language}
{code}
```

请检查以下安全风险：
- SQL注入
- XSS攻击
- CSRF攻击
- 敏感信息泄露
- 权限控制问题

请详细列出发现的安全问题并提供修复建议。"""
        },
        "performance": {
            "prompt": """请对以下代码进行性能分析和优化建议：

```{language}
{code}
```

请分析：
- 时间复杂度
- 空间复杂度
- 可能的性能瓶颈
- 优化建议

请提供具体的优化代码示例。"""
        },
        "full": {
            "prompt": """请对以下代码进行全面审查：

```{language}
{code}
```

请从以下维度进行审查：
1. **代码质量**：命名规范、代码风格、注释
2. **潜在问题**：bug、边界条件、异常处理
3. **安全问题**：注入攻击、敏感数据、安全配置
4. **性能问题**：算法效率、资源占用、缓存策略
5. **最佳实践**：设计模式、架构设计、可测试性
6. **可维护性**：模块化、依赖管理、文档

请以结构化报告形式输出。"""
        }
    }
    
    # ========== 数据分析模板 ==========
    
    DATA_ANALYSIS_SYSTEM = """你是一位专业的数据分析师，擅长从数据中提取洞察并生成有价值的报告。
请根据用户提供的分析需求和数据，进行全面的数据分析并生成报告。

报告要求：
1. 结构清晰，包含执行摘要
2. 使用图表描述数据（用文字形式表示）
3. 提供可操作的洞察和建议
4. 结论要有数据支撑"""
    
    DATA_ANALYSIS_TEMPLATES = {
        "trend": {
            "prompt": """请分析以下数据的时间趋势：

```
{data}
```

分析维度：
1. 总体趋势判断
2. 周期性变化
3. 异常点识别
4. 预测和建议

请生成详细的分析报告。"""
        },
        "comparison": {
            "prompt": """请对比分析以下两组数据：

**组A：**
{data_a}

**组B：**
{data_b}

分析维度：
1. 基本统计对比
2. 差异分析
3. 原因推断
4. 建议

请生成对比分析报告。"""
        },
        "distribution": {
            "prompt": """请分析以下数据的分布特征：

```
{data}
```

分析维度：
1. 分布形态（正态/偏态/均匀）
2. 集中趋势（均值/中位数/众数）
3. 离散程度（方差/标准差/极值）
4. 异常值检测
5. 分布可视化建议

请生成分析报告。"""
        },
        "correlation": {
            "prompt": """请分析以下多维数据的相关性：

```
{data}
```

分析维度：
1. 变量间的相关关系
2. 强相关/弱相关识别
3. 相关性方向（正/负）
4. 潜在因果关系推断
5. 建模建议

请生成相关性分析报告。"""
        },
        "full_report": {
            "prompt": """请对以下数据进行全面的数据分析并生成报告：

```
{data}
```

报告结构：
1. 执行摘要
2. 数据概览
3. 描述性统计
4. 趋势分析
5. 模式识别
6. 异常检测
7. 洞察与发现
8. 建议与行动方案

请生成专业的分析报告，包含具体的数据支撑。"""
        }
    }
    
    # ========== 智能对话模板 ==========
    
    SMART_CHAT_SYSTEM = """你是一位智能助手，擅长理解和回答各种问题。
请根据对话上下文和用户问题，提供准确、有帮助的回答。

回答原则：
1. 准确理解用户意图
2. 提供有用的信息
3. 保持对话连贯性
4. 适时提问澄清
5. 复杂问题分步骤解答"""
    
    # ========== 辅助方法 ==========
    
    @classmethod
    def get_content_prompt(
        cls,
        content_type: str,
        topic: str,
        length: str = "medium",
        style: str = "professional",
        **kwargs
    ) -> str:
        """生成内容创作提示词"""
        template = cls.CONTENT_WRITE_TEMPLATES.get(content_type, {})
        
        if isinstance(template, dict):
            template = template.get(length, template.get("medium", ""))
        
        if "{keyword}" in template:
            template = template.format(
                keyword=kwargs.get("keyword", ""),
                count=kwargs.get("count", 5)
            )
        elif "{product}" in template:
            template = template.format(
                product=topic,
                audience=kwargs.get("audience", ""),
                type=kwargs.get("content_type", "产品介绍"),
                style=style,
                selling_points=kwargs.get("selling_points", "")
            )
        else:
            template = template.format(topic=topic, style=style)
        
        return template
    
    @classmethod
    def get_code_review_prompt(
        cls,
        code: str,
        language: str,
        focus_areas: List[str] = None,
        model: str = "basic"
    ) -> str:
        """生成代码审查提示词"""
        focus_areas = focus_areas or ["basic"]
        
        # 根据关注点组合模板
        if "security" in focus_areas and "performance" in focus_areas:
            template = cls.CODE_REVIEW_TEMPLATES["full"]["prompt"]
        elif "security" in focus_areas:
            template = cls.CODE_REVIEW_TEMPLATES["security"]["prompt"]
        elif "performance" in focus_areas:
            template = cls.CODE_REVIEW_TEMPLATES["performance"]["prompt"]
        else:
            template = cls.CODE_REVIEW_TEMPLATES["basic"]["prompt"]
        
        return template.format(code=code, language=language, model=model)
    
    @classmethod
    def get_data_analysis_prompt(
        cls,
        data: str,
        analysis_type: str = "trend",
        report_format: str = "standard",
        **kwargs
    ) -> str:
        """生成数据分析提示词"""
        template = cls.DATA_ANALYSIS_TEMPLATES.get(analysis_type, cls.DATA_ANALYSIS_TEMPLATES["trend"])
        
        if isinstance(template, dict):
            template = template.get("prompt", "")
        
        return template.format(data=data, **kwargs)


# 全局模板实例
prompt_templates = PromptTemplates()
