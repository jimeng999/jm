"""
x402 支付协议服务模块
HTTP 402 Payment Required 协议实现
使用 USDC 稳定币在 Base 链上按请求实时结算
"""
import json
import httpx
from typing import Optional, Dict, Any, Tuple

from config import settings, model_config
from utils.logger import logger


class X402Service:
    """x402 支付协议服务"""
    
    # Coinbase 官方 Facilitator 验证端点
    FACILITATOR_URL = "https://facilitator.x402.org/verify"
    
    # x402 协议版本
    X402_VERSION = 1
    
    def __init__(self):
        self.enabled = settings.x402_enabled
        self.wallet_address = settings.x402_wallet_address
        self.network = settings.x402_network
        self.usdc_contract = model_config.USDC_BASE_CONTRACT
    
    def is_enabled(self) -> bool:
        """检查 x402 是否启用"""
        return self.enabled
    
    def get_pricing_for_model(self, model: str) -> Optional[Dict[str, str]]:
        """获取模型的 x402 定价"""
        return model_config.X402_PRICING.get(model)
    
    def build_payment_required_response(
        self, 
        resource: str, 
        model: str = "gpt-4o-mini"
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        构建 HTTP 402 Payment Required 响应
        
        返回: (响应体, headers)
        """
        pricing = self.get_pricing_for_model(model)
        if not pricing:
            # 如果模型没有配置定价，使用默认定价
            pricing = {
                "amount": "10000",
                "usd": "$0.01",
                "description": f"{model} per request"
            }
        
        response_body = {
            "x402Version": self.X402_VERSION,
            "accepts": {
                "scheme": "exact",
                "network": self.network,
                "maxAmountRequired": pricing["amount"],
                "asset": self.usdc_contract,
                "payTo": self.wallet_address,
                "resource": resource,
                "description": f"AI API Gateway - {pricing['description']}"
            }
        }
        
        headers = {
            "PAYMENT-REQUIRED": json.dumps(response_body),
            "Access-Control-Expose-Headers": "PAYMENT-REQUIRED, PAYMENT-RESPONSE"
        }
        
        return response_body, headers
    
    async def verify_payment(
        self, 
        payment_signature: str, 
        resource: str,
        model: str = "gpt-4o-mini"
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        验证 x402 支付签名
        
        调用 Coinbase 官方 Facilitator 验证支付
        返回: (验证是否通过, 验证详情)
        """
        pricing = self.get_pricing_for_model(model)
        if not pricing:
            pricing = {
                "amount": "10000",
                "usd": "$0.01",
                "description": f"{model} per request"
            }
        
        try:
            # 解析 payment signature (base64 encoded JSON payload)
            import base64
            try:
                payload_json = base64.b64decode(payment_signature)
                payment_payload = json.loads(payload_json)
            except Exception:
                # 如果不是 base64，尝试直接解析 JSON
                try:
                    payment_payload = json.loads(payment_signature)
                except Exception:
                    logger.warning(f"x402: Invalid payment signature format")
                    return False, {"error": "Invalid payment signature format"}
            
            # 构建验证请求
            verify_request = {
                "paymentPayload": payment_payload,
                "requirements": {
                    "scheme": "exact",
                    "network": self.network,
                    "maxAmountRequired": pricing["amount"],
                    "asset": self.usdc_contract,
                    "payTo": self.wallet_address,
                    "resource": resource
                }
            }
            
            # 调用 Facilitator 验证
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.FACILITATOR_URL,
                    json=verify_request,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    is_valid = result.get("isValid", False)
                    
                    if is_valid:
                        logger.info(f"x402: Payment verified for {resource} (model: {model})")
                        return True, result
                    else:
                        logger.warning(f"x402: Payment verification failed - {result}")
                        return False, result
                else:
                    logger.error(f"x402: Facilitator returned {response.status_code}: {response.text}")
                    return False, {"error": f"Facilitator returned {response.status_code}"}
                    
        except httpx.TimeoutException:
            logger.error("x402: Facilitator request timed out")
            return False, {"error": "Facilitator request timed out"}
        except Exception as e:
            logger.error(f"x402: Payment verification error: {str(e)}")
            return False, {"error": str(e)}
    
    def build_payment_response_header(self, verification_result: Dict[str, Any]) -> str:
        """构建 PAYMENT-RESPONSE header"""
        return json.dumps({
            "x402Version": self.X402_VERSION,
            "success": True,
            "verification": verification_result
        })


# 全局 x402 服务实例
x402_service = X402Service()
