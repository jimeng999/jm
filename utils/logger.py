"""
日志工具模块
"""
import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(name: str = "ai_gateway", level: int = logging.INFO) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
    
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    # 控制台输出格式
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # 详细的日志格式
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


# 创建默认日志记录器
logger = setup_logger("ai_gateway", logging.INFO)


class RequestLogger:
    """请求日志记录器"""
    
    def __init__(self, log_dir: Path = Path("./logs")):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._init_file_handler()
    
    def _init_file_handler(self):
        """初始化文件处理器"""
        today = datetime.now().strftime("%Y%m%d")
        log_file = self.log_dir / f"requests_{today}.log"
        
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        
        self.logger = logging.getLogger("request_logger")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
    
    def log_request(self, user_id: str, endpoint: str, model: str = None, 
                   tokens_used: int = 0, cost: float = 0, status: str = "success"):
        """记录 API 请求"""
        msg = f"user={user_id} | endpoint={endpoint} | model={model} | tokens={tokens_used} | cost={cost:.4f} | status={status}"
        self.logger.info(msg)
    
    def log_error(self, user_id: str, endpoint: str, error: str):
        """记录错误"""
        msg = f"user={user_id} | endpoint={endpoint} | error={error}"
        self.logger.error(msg)


# 全局请求日志记录器
request_logger = RequestLogger()
