"""
Custom exceptions for SAP integration
SAP 集成自定义异常
"""


class SAPIntegrationError(Exception):
    """Base exception for SAP integration errors"""
    pass


class SAPConnectionError(SAPIntegrationError):
    """SAP connection failed"""
    pass


class SAPAuthenticationError(SAPIntegrationError):
    """SAP authentication failed"""
    pass


class SAPDataError(SAPIntegrationError):
    """SAP data extraction or parsing error"""
    pass


class SAPTimeoutError(SAPIntegrationError):
    """SAP request timeout"""
    pass


class SAPServiceNotFoundError(SAPIntegrationError):
    """SAP OData service not found"""
    pass
