#!/usr/bin/env python3
# exceptions.py - 自定义异常类

class QuotaExceededException(Exception):
    """Quota超限异常"""
    
    def __init__(self, message: str, original_model: str = None, fallback_model: str = None, instance_id: str = None):
        super().__init__(message)
        self.original_model = original_model
        self.fallback_model = fallback_model
        self.instance_id = instance_id
        
    def __str__(self):
        return f"QuotaExceededException: {super().__str__()}"
        
class ClientDisconnectedError(Exception):
    """客户端断开连接异常"""
    pass