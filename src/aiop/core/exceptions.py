"""
Custom exceptions for AIOP
"""

from typing import Optional


class AIOPError(Exception):
    """Base exception for AIOP"""
    
    def __init__(self, message: str, code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.code = code


class AudioError(AIOPError):
    """Audio-related exceptions"""
    pass


class SpeechError(AIOPError):
    """Speech recognition exceptions"""
    pass


class WindowsError(AIOPError):
    """Windows integration exceptions"""
    pass


class AIError(AIOPError):
    """AI-related exceptions"""
    pass


class AutomationError(AIOPError):
    """Automation exceptions"""
    pass


class PluginError(AIOPError):
    """Plugin-related exceptions"""
    pass


class MCPError(AIOPError):
    """MCP-related exceptions"""
    pass


class ConfigurationError(AIOPError):
    """Configuration exceptions"""
    pass


class ResourceNotFoundError(AIOPError):
    """Resource not found exceptions"""
    
    def __init__(self, resource_type: str, resource_name: str):
        message = f"{resource_type} '{resource_name}' not found"
        super().__init__(message)
        self.resource_type = resource_type
        self.resource_name = resource_name


class PermissionError(AIOPError):
    """Permission-related exceptions"""
    
    def __init__(self, permission: str, message: Optional[str] = None):
        msg = message or f"Permission denied: {permission}"
        super().__init__(msg)
        self.permission = permission


class TimeoutError(AIOPError):
    """Timeout exceptions"""
    
    def __init__(self, operation: str, timeout: float):
        message = f"Operation '{operation}' timed out after {timeout} seconds"
        super().__init__(message)
        self.operation = operation
        self.timeout = timeout


class ModelError(AIOPError):
    """Model-related exceptions"""
    pass


class ConnectionError(AIOPError):
    """Connection-related exceptions"""
    pass
