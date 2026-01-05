"""
SAP OData Client
SAP OData 客户端 - 负责与 SAP 系统通信
"""
import requests
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger
import time
from urllib.parse import urljoin, quote

from .exceptions import (
    SAPConnectionError,
    SAPAuthenticationError,
    SAPDataError,
    SAPTimeoutError,
    SAPServiceNotFoundError
)


class SAPODataClient:
    """SAP OData API 客户端"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 SAP 客户端
        
        Args:
            config: SAP 配置字典
        """
        self.host = config['sap']['host']
        self.port = config['sap']['port']
        self.protocol = config['sap']['protocol']
        self.client = config['sap']['client']
        
        self.base_url = f"{self.protocol}://{self.host}:{self.port}"
        
        # 认证配置
        auth_config = config['sap']['auth']
        self.auth_type = auth_config['type']
        self.username = auth_config.get('username')
        self.password = auth_config.get('password')
        
        # 服务路径
        self.services = config['sap']['services']
        
        # 请求配置
        req_config = config['sap']['request']
        self.timeout = req_config.get('timeout', 30)
        self.verify_ssl = req_config.get('verify_ssl', True)
        self.max_retries = req_config.get('max_retries', 3)
        self.retry_delay = req_config.get('retry_delay', 5)
        
        # Session
        self.session = requests.Session()
        self._setup_auth()
    
    def _setup_auth(self):
        """设置认证"""
        if self.auth_type == 'basic':
            credentials = f"{self.username}:{self.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            self.session.headers.update({
                'Authorization': f'Basic {encoded}'
            })
        elif self.auth_type == 'oauth':
            # OAuth token 获取逻辑
            token = self._get_oauth_token()
            self.session.headers.update({
                'Authorization': f'Bearer {token}'
            })
        
        # 通用 headers
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'sap-client': self.client
        })
    
    def _get_oauth_token(self) -> str:
        """获取 OAuth token（待实现）"""
        # TODO: 实现 OAuth 2.0 token 获取
        raise NotImplementedError("OAuth authentication not yet implemented")
    
    def test_connection(self) -> bool:
        """
        测试 SAP 连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 尝试访问服务根路径
            url = urljoin(self.base_url, self.services['production_orders'])
            response = self.session.get(
                url,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            if response.status_code == 200:
                logger.info("✓ SAP 连接测试成功")
                return True
            elif response.status_code == 401:
                raise SAPAuthenticationError("认证失败，请检查用户名密码")
            elif response.status_code == 404:
                raise SAPServiceNotFoundError(f"OData 服务不存在: {url}")
            else:
                raise SAPConnectionError(f"连接失败: HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            raise SAPTimeoutError(f"连接超时（>{self.timeout}秒）")
        except requests.exceptions.ConnectionError as e:
            raise SAPConnectionError(f"无法连接到 SAP 服务器: {e}")
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict:
        """
        发送 HTTP 请求（带重试）
        
        Args:
            url: 请求 URL
            params: 查询参数
            
        Returns:
            响应 JSON 数据
        """
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                    verify=self.verify_ssl
                )
                
                # 检查状态码
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    raise SAPAuthenticationError("认证失败")
                elif response.status_code == 404:
                    raise SAPServiceNotFoundError(f"服务不存在: {url}")
                else:
                    logger.warning(f"请求失败: HTTP {response.status_code}, 尝试 {attempt + 1}/{self.max_retries}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"请求超时, 尝试 {attempt + 1}/{self.max_retries}")
            except requests.exceptions.RequestException as e:
                logger.warning(f"请求异常: {e}, 尝试 {attempt + 1}/{self.max_retries}")
            
            # 重试前等待
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        raise SAPConnectionError(f"请求失败，已重试 {self.max_retries} 次")
    
    def get_production_orders(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        top: int = 1000,
        skip: int = 0,
        filter_str: Optional[str] = None
    ) -> List[Dict]:
        """
        获取生产订单数据
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            top: 每页记录数
            skip: 跳过记录数
            filter_str: 自定义过滤条件
            
        Returns:
            订单列表
        """
        logger.info(f"获取生产订单: start={start_date}, end={end_date}, top={top}, skip={skip}")
        
        # 构建 URL
        service_url = urljoin(self.base_url, self.services['production_orders'])
        entity_url = urljoin(service_url + '/', 'ProductionOrderSet')
        
        # 构建过滤条件
        filters = []
        
        # 必须有实际完成日期
        filters.append("ActualFinishDate ne null")
        
        # 日期范围
        if start_date:
            filters.append(f"BasicStartDate ge datetime'{start_date}T00:00:00'")
        if end_date:
            filters.append(f"BasicStartDate le datetime'{end_date}T23:59:59'")
        
        # 自定义过滤
        if filter_str:
            filters.append(filter_str)
        
        # 组合过滤条件
        filter_query = " and ".join(filters) if filters else None
        
        # 查询参数
        params = {
            '$format': 'json',
            '$top': top,
            '$skip': skip,
            '$orderby': 'BasicStartDate desc'
        }
        
        if filter_query:
            params['$filter'] = filter_query
        
        # 发送请求
        try:
            data = self._make_request(entity_url, params)
            
            # 解析结果
            if 'd' in data and 'results' in data['d']:
                results = data['d']['results']
                logger.info(f"✓ 成功获取 {len(results)} 条订单")
                return results
            else:
                logger.warning("响应格式异常，未找到 results")
                return []
                
        except Exception as e:
            logger.error(f"获取生产订单失败: {e}")
            raise SAPDataError(f"数据提取失败: {e}")
    
    def get_all_production_orders(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        batch_size: int = 1000
    ) -> List[Dict]:
        """
        获取所有生产订单（自动分页）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            batch_size: 每批数量
            
        Returns:
            所有订单列表
        """
        all_orders = []
        skip = 0
        
        logger.info(f"开始分页获取订单: start_date={start_date}, batch_size={batch_size}")
        
        while True:
            batch = self.get_production_orders(
                start_date=start_date,
                end_date=end_date,
                top=batch_size,
                skip=skip
            )
            
            if not batch:
                break
            
            all_orders.extend(batch)
            skip += batch_size
            
            logger.info(f"已获取 {len(all_orders)} 条订单...")
            
            # 如果返回数量少于批次大小，说明已经是最后一批
            if len(batch) < batch_size:
                break
        
        logger.info(f"✓ 总共获取 {len(all_orders)} 条订单")
        return all_orders
    
    def get_material_master(self) -> List[Dict]:
        """
        获取物料主数据
        
        Returns:
            物料列表
        """
        logger.info("获取物料主数据")
        
        service_url = urljoin(self.base_url, self.services['material_master'])
        entity_url = urljoin(service_url + '/', 'MaterialSet')
        
        params = {
            '$format': 'json',
            '$select': 'MaterialNumber,MaterialDescription,ProductionLine,ConstraintFactor,EarliestStartDays,TotalProductionTime'
        }
        
        try:
            data = self._make_request(entity_url, params)
            
            if 'd' in data and 'results' in data['d']:
                results = data['d']['results']
                logger.info(f"✓ 成功获取 {len(results)} 条物料数据")
                return results
            else:
                return []
                
        except Exception as e:
            logger.error(f"获取物料主数据失败: {e}")
            raise SAPDataError(f"物料数据提取失败: {e}")
    
    def get_line_capacity(self) -> List[Dict]:
        """
        获取产线产能数据
        
        Returns:
            产线产能列表
        """
        logger.info("获取产线产能数据")
        
        service_url = urljoin(self.base_url, self.services['line_capacity'])
        entity_url = urljoin(service_url + '/', 'CapacitySet')
        
        params = {
            '$format': 'json'
        }
        
        try:
            data = self._make_request(entity_url, params)
            
            if 'd' in data and 'results' in data['d']:
                results = data['d']['results']
                logger.info(f"✓ 成功获取 {len(results)} 条产能数据")
                return results
            else:
                return []
                
        except Exception as e:
            logger.error(f"获取产线产能失败: {e}")
            raise SAPDataError(f"产能数据提取失败: {e}")
    
    def get_metadata(self, service_name: str) -> Dict:
        """
        获取 OData 服务元数据
        
        Args:
            service_name: 服务名称 (production_orders / material_master / line_capacity)
            
        Returns:
            元数据字典
        """
        service_url = urljoin(self.base_url, self.services[service_name])
        metadata_url = urljoin(service_url + '/', '$metadata')
        
        try:
            response = self.session.get(
                metadata_url,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            if response.status_code == 200:
                logger.info(f"✓ 成功获取 {service_name} 元数据")
                return {'xml': response.text}
            else:
                raise SAPServiceNotFoundError(f"服务元数据不存在: {metadata_url}")
                
        except Exception as e:
            logger.error(f"获取元数据失败: {e}")
            raise
