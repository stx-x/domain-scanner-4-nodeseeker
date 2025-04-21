#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
rdap_client.py

RDAP协议客户端，负责通过HTTP HEAD请求检查域名可用性。
提供与各种RDAP服务器通信的功能，并解析HTTP状态码。
"""

import time
import requests
from typing import Dict, Any, Tuple, Optional, List
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("rdap_client")

# RDAP服务器配置
RDAP_SERVERS = {
    # 瑞士和列支敦士登域名
    '.ch': 'https://rdap.nic.ch/domain/',
    '.li': 'https://rdap.nic.ch/domain/',

    # 德国域名
    '.de': 'https://rdap.denic.de/domain/',

    # 通用顶级域名
    '.com': 'https://rdap.verisign.com/com/v1/domain/',
    '.net': 'https://rdap.verisign.com/net/v1/domain/',
    '.org': 'https://rdap.pir.org/v1/domain/',

    # 其它
    '.cc': 'https://tld-rdap.verisign.com/$TLD/v1/domain/',
    '.name': 'https://tld-rdap.verisign.com/$TLD/v1/domain/',

    # 添加更多TLD及其RDAP服务器 google TLD + rdap，比如 .cn rdap
}

# HTTP状态码与域名状态映射
STATUS_CODES = {
    200: {'available': False, 'status': 'registered', 'status_cn': '已被注册'},
    401: {'available': False, 'status': 'registered', 'status_cn': '已被注册 (需要授权)'},
    404: {'available': True, 'status': 'available', 'status_cn': '可以注册'},
    400: {'available': False, 'status': 'invalid_request', 'status_cn': '无效请求 (域名格式错误)'},
    429: {'available': False, 'status': 'rate_limited', 'status_cn': '查询频率限制 (请稍后重试)'},
    403: {'available': False, 'status': 'forbidden', 'status_cn': '服务器拒绝访问'},
    500: {'available': False, 'status': 'server_error', 'status_cn': '服务器错误 (请稍后重试)'},
    503: {'available': False, 'status': 'service_unavailable', 'status_cn': '服务不可用 (请稍后重试)'},
}

class RdapClient:
    """RDAP客户端，用于检查域名可用性"""

    def __init__(self, max_retries: int = 2, timeout: int = 10, user_agent: Optional[str] = None):
        """
        初始化RDAP客户端

        参数:
            max_retries: 查询失败时的最大重试次数
            timeout: 请求超时时间(秒)
            user_agent: 自定义User-Agent字符串
        """
        self.max_retries = max_retries
        self.timeout = timeout

        # 设置默认请求头
        self.headers = {
            'User-Agent': user_agent or 'Domain-Availability-Scanner/1.0',
            'Accept': 'application/rdap+json'
        }

        # 用于记录每个服务器的最后查询时间
        self.last_query_time: Dict[str, float] = {}

        # 会话对象，用于保持连接
        self.session = requests.Session()

    def check_domain(self, domain: str, retry_count: int = 0) -> Dict[str, Any]:
        """
        检查域名可用性

        通过向RDAP服务器发送HEAD请求并分析HTTP状态码来确定域名状态

        参数:
            domain: 完整域名 (例如: 'example.com')
            retry_count: 内部重试计数

        返回:
            包含查询结果的字典:
            {
                'domain': 完整域名,
                'available': 布尔值，表示是否可注册,
                'status': 英文状态描述,
                'status_cn': 中文状态描述,
                'tld': 顶级域名,
                'raw_code': HTTP状态码,
                'response_time': 响应时间(毫秒),
                'error': 错误信息 (如有)
            }
        """
        # 准备结果字典
        result = {
            'domain': domain,
            'available': False,
            'status': 'unknown',
            'status_cn': '未知状态',
            'tld': None,
            'raw_code': None,
            'response_time': None,
            'error': None
        }

        # 提取TLD
        tld = self._extract_tld(domain)
        result['tld'] = tld

        # 检查是否支持该TLD
        if tld not in RDAP_SERVERS:
            result['status'] = 'unsupported_tld'
            result['status_cn'] = f'不支持的顶级域名: {tld}'
            result['error'] = f'未配置{tld}的RDAP服务器'
            return result

        # 构建RDAP URL
        rdap_url = RDAP_SERVERS[tld] + domain

        # 确保请求间隔 (防止速率限制)
        self._ensure_query_delay(tld)

        # 记录开始时间
        start_time = time.time()

        try:
            # 发送HEAD请求
            response = self.session.head(
                rdap_url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True  # 允许重定向
            )

            # 更新最后查询时间
            self.last_query_time[tld] = time.time()

            # 计算响应时间 (毫秒)
            response_time = (time.time() - start_time) * 1000
            result['response_time'] = round(response_time, 2)

            # 获取状态码
            status_code = response.status_code
            result['raw_code'] = status_code

            # 解析状态码
            if status_code in STATUS_CODES:
                status_info = STATUS_CODES[status_code].copy()
                result.update(status_info)
            else:
                # 处理未知状态码
                result['status'] = 'unknown_status_code'
                result['status_cn'] = f'未知状态码: {status_code}'
                result['error'] = f'RDAP服务器返回未知状态码: {status_code}'

            return result

        except requests.exceptions.Timeout:
            # 处理超时错误
            result['status'] = 'timeout'
            result['status_cn'] = '查询超时'
            result['error'] = f'连接{rdap_url}超时 ({self.timeout}秒)'

            # 尝试重试
            if retry_count < self.max_retries:
                logger.warning(f"查询{domain}超时，正在重试 ({retry_count + 1}/{self.max_retries})...")
                time.sleep(1)  # 重试前等待1秒
                return self.check_domain(domain, retry_count + 1)

        except requests.exceptions.ConnectionError as e:
            # 处理连接错误
            result['status'] = 'connection_error'
            result['status_cn'] = '连接错误'
            result['error'] = f'连接到{rdap_url}时发生错误: {str(e)}'

            # 尝试重试
            if retry_count < self.max_retries:
                logger.warning(f"连接到{domain}时出错，正在重试 ({retry_count + 1}/{self.max_retries})...")
                time.sleep(1)  # 重试前等待1秒
                return self.check_domain(domain, retry_count + 1)

        except Exception as e:
            # 处理其他错误
            result['status'] = 'error'
            result['status_cn'] = '查询错误'
            result['error'] = f'查询{domain}时发生错误: {str(e)}'

            # 尝试重试
            if retry_count < self.max_retries:
                logger.warning(f"查询{domain}时发生错误，正在重试 ({retry_count + 1}/{self.max_retries})...")
                time.sleep(1)  # 重试前等待1秒
                return self.check_domain(domain, retry_count + 1)

        finally:
            # 无论成功失败，都更新最后查询时间
            self.last_query_time[tld] = time.time()

        return result

    def _extract_tld(self, domain: str) -> str:
        """
        从完整域名中提取顶级域名

        参数:
            domain: 完整域名 (例如: 'example.com')

        返回:
            顶级域名 (例如: '.com')
        """
        # 简单实现：获取最后一个点之后的部分
        parts = domain.split('.')
        if len(parts) >= 2:
            return f'.{parts[-1]}'

        # 无法确定TLD
        return ''

    def _ensure_query_delay(self, tld: str) -> None:
        """
        确保对同一TLD的查询有足够的时间间隔
        防止触发RDAP服务器的速率限制

        参数:
            tld: 顶级域名
        """
        if tld in self.last_query_time:
            last_time = self.last_query_time[tld]
            now = time.time()
            elapsed = now - last_time

            # 默认每个TLD的最小查询间隔为1.0秒
            # 可以为不同TLD设置不同的间隔
            min_interval = 1.0

            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)

    def get_supported_tlds(self) -> List[str]:
        """
        获取当前支持的顶级域名列表

        返回:
            支持的顶级域名列表
        """
        return list(RDAP_SERVERS.keys())

    def close(self) -> None:
        """关闭连接会话"""
        if self.session:
            self.session.close()

# 测试代码
if __name__ == "__main__":
    # 简单的测试函数
    def test_rdap_client():
        client = RdapClient()

        # 测试一个可能已注册的域名
        print("检查已知域名...")
        result = client.check_domain("google.com")
        print(f"Domain: {result['domain']}")
        print(f"Status: {result['status']} ({result['status_cn']})")
        print(f"Available: {result['available']}")
        print(f"Response time: {result['response_time']} ms")
        print(f"Raw code: {result['raw_code']}")
        print()

        # 测试一个可能未注册的域名 (随机生成)
        import random
        import string
        random_domain = ''.join(random.choices(string.ascii_lowercase, k=10)) + ".com"
        print(f"检查随机域名: {random_domain}...")
        result = client.check_domain(random_domain)
        print(f"Domain: {result['domain']}")
        print(f"Status: {result['status']} ({result['status_cn']})")
        print(f"Available: {result['available']}")
        print(f"Response time: {result['response_time']} ms")
        print(f"Raw code: {result['raw_code']}")

        # 关闭客户端
        client.close()

    test_rdap_client()
