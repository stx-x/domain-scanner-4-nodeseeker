#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
rdap_client.py

增强版RDAP协议客户端，支持直接查询特定TLD和通过RDAP.org查询通用TLD。
提供高效、可靠的域名可用性检测，支持各种顶级域名(TLD)。
"""

import time
import requests
from typing import Dict, Any, Tuple, Optional, List, Set
import logging
import re

# 配置日志
logger = logging.getLogger("rdap_client")

# RDAP服务配置
RDAP_ORG_URL = "https://rdap.org/domain/{domain}"  # RDAP.org统一入口
RDAP_IANA_URL = "https://rdap.iana.org/domain/{domain}"  # IANA RDAP服务

# 特定TLD的直接RDAP服务器 (优先使用这些服务器)
DIRECT_RDAP_SERVERS = {
    '.ch': 'https://rdap.nic.ch/domain/{domain}',
    '.li': 'https://rdap.nic.ch/domain/{domain}',
    '.de': 'https://rdap.denic.de/domain/{domain}',
    # 可以根据需要添加更多TLD
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
    302: {'available': False, 'status': 'redirect', 'status_cn': '重定向 (跟随Location)'},
}

# 预编译域名验证正则表达式
DOMAIN_REGEX = re.compile(r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$')

# 服务器查询延迟配置 (秒)
SERVER_DELAY = {
    'rdap.org': 1.0,
    'iana': 1.0,
    '.ch': 1.0,
    '.li': 1.0,
    '.de': 1.0,
    'default': 1.0  # 默认延迟
}


class RdapClient:
    """增强的RDAP客户端，支持特定TLD直接查询和通用TLD查询"""

    def __init__(self, max_retries: int = 2, timeout: int = 10,
                user_agent: Optional[str] = None, prefer_direct: bool = True):
        """
        初始化RDAP客户端

        参数:
            max_retries: 查询失败时的最大重试次数
            timeout: 请求超时时间(秒)
            user_agent: 自定义User-Agent字符串
            prefer_direct: 是否优先使用直接RDAP服务器 (对于已知TLD)
        """
        self.max_retries = max_retries
        self.timeout = timeout
        self.prefer_direct = prefer_direct

        # 设置默认请求头
        self.headers = {
            'User-Agent': user_agent or 'DomainSeeker/2.0 (https://github.com/yourusername/domainseeker)',
            'Accept': 'application/rdap+json'
        }

        # 用于记录每个服务器的最后查询时间
        self.last_query_time: Dict[str, float] = {}

        # 会话对象，用于保持连接
        self.session = requests.Session()

        # 已知的TLD缓存，避免重复查询
        self.known_tlds: Set[str] = set(DIRECT_RDAP_SERVERS.keys())

        logger.info("RDAP客户端初始化完成")
        if prefer_direct:
            logger.info("优先使用特定TLD的RDAP服务器")
        else:
            logger.info("优先使用RDAP.org作为查询入口")

    def check_domain(self, domain: str, retry_count: int = 0) -> Dict[str, Any]:
        """
        检查域名可用性

        通过RDAP协议检查域名状态，支持所有TLD。
        对已知TLD优先使用直接服务器，对其他TLD使用RDAP.org。

        参数:
            domain: 完整域名 (例如: 'example.com')
            retry_count: 内部重试计数

        返回:
            包含查询结果的字典:
            {
                'domain': 完整域名,
                'available': 是否可注册,
                'status': 英文状态描述,
                'status_cn': 中文状态描述,
                'tld': 顶级域名,
                'raw_code': HTTP状态码,
                'response_time': 响应时间(毫秒),
                'error': 错误信息 (如有),
                'rdap_server': 使用的RDAP服务器
            }
        """
        # 格式化域名(转为小写)
        domain = domain.lower()

        # 准备结果字典
        result = {
            'domain': domain,
            'available': False,
            'status': 'unknown',
            'status_cn': '未知状态',
            'tld': None,
            'raw_code': None,
            'response_time': None,
            'error': None,
            'rdap_server': None
        }

        # 验证域名格式
        if not self._is_valid_domain(domain):
            result['status'] = 'invalid_domain'
            result['status_cn'] = '无效的域名格式'
            result['error'] = f'域名 {domain} 格式无效'
            return result

        # 提取TLD
        tld = self._extract_tld(domain)
        result['tld'] = tld

        # 确定使用哪个RDAP服务器
        rdap_url, server_type = self._get_rdap_server_url(domain, tld)
        result['rdap_server'] = server_type

        # 确保请求间隔 (防止速率限制)
        self._ensure_query_delay(server_type)

        # 记录开始时间
        start_time = time.time()

        try:
            # 发送HEAD请求
            response = self.session.head(
                rdap_url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=False  # 不自动跟随重定向，手动处理
            )

            # 更新最后查询时间
            self.last_query_time[server_type] = time.time()

            # 计算响应时间 (毫秒)
            response_time = (time.time() - start_time) * 1000
            result['response_time'] = round(response_time, 2)

            # 获取状态码
            status_code = response.status_code
            result['raw_code'] = status_code

            # 处理RDAP.org的响应
            if server_type == 'rdap.org':
                if status_code == 302:
                    # RDAP.org知道有RDAP服务，跟随重定向
                    redirect_url = response.headers.get('Location')
                    if redirect_url:
                        logger.debug(f"RDAP.org重定向到: {redirect_url}")
                        result['redirect_url'] = redirect_url

                        # 确保请求间隔
                        time.sleep(0.5)

                        try:
                            # 发送请求到重定向目标
                            redirect_response = self.session.head(
                                redirect_url,
                                headers=self.headers,
                                timeout=self.timeout
                            )

                            # 使用重定向目标的状态码
                            status_code = redirect_response.status_code
                            result['raw_code'] = status_code
                            result['rdap_server'] = 'redirect_target'

                            # 解析重定向目标的状态码
                            if status_code == 404:
                                # 大多数RDAP服务器用404表示域名未注册
                                result['status'] = 'available'
                                result['status_cn'] = '可以注册'
                                result['available'] = True
                            elif status_code in STATUS_CODES:
                                # 使用预定义的状态码解释
                                status_info = STATUS_CODES[status_code].copy()
                                result.update(status_info)
                            else:
                                # 未知状态码
                                result['status'] = 'unknown_status_code'
                                result['status_cn'] = f'未知状态码: {status_code}'
                                result['error'] = f'RDAP服务器返回未知状态码: {status_code}'

                        except Exception as e:
                            logger.warning(f"跟随重定向时出错: {e}")
                            result['status'] = 'redirect_error'
                            result['status_cn'] = '重定向错误'
                            result['error'] = f'跟随重定向时出错: {e}'

                elif status_code == 404:
                    # RDAP.org不知道有RDAP服务，表示该TLD没有已知的RDAP服务
                    result['status'] = 'no_rdap_service'
                    result['status_cn'] = 'TLD无已知RDAP服务'
                    result['available'] = False
                    result['error'] = f'{tld}没有已知的RDAP服务，无法通过RDAP确认域名状态'

                elif status_code in STATUS_CODES:
                    # 对于其他状态码使用预定义解释
                    status_info = STATUS_CODES[status_code].copy()
                    result.update(status_info)

                else:
                    # 未知状态码
                    result['status'] = 'unknown_status_code'
                    result['status_cn'] = f'未知状态码: {status_code}'
                    result['error'] = f'RDAP.org返回未知状态码: {status_code}'

            # 对于直接RDAP服务器的响应
            else:
                if status_code in STATUS_CODES:
                    status_info = STATUS_CODES[status_code].copy()
                    result.update(status_info)
                else:
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

            # 如果重试都失败并且是使用直接服务器，尝试使用RDAP.org
            elif server_type.startswith('direct_') and self.prefer_direct:
                logger.warning(f"直接查询{domain}失败，尝试使用RDAP.org...")
                # 临时关闭prefer_direct标志
                old_prefer = self.prefer_direct
                self.prefer_direct = False
                try:
                    return self.check_domain(domain, 0)  # 重置重试计数
                finally:
                    # 恢复原始设置
                    self.prefer_direct = old_prefer

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

            # 如果重试都失败并且是使用直接服务器，尝试使用RDAP.org
            elif server_type.startswith('direct_') and self.prefer_direct:
                logger.warning(f"直接查询{domain}失败，尝试使用RDAP.org...")
                # 临时关闭prefer_direct标志
                old_prefer = self.prefer_direct
                self.prefer_direct = False
                try:
                    return self.check_domain(domain, 0)  # 重置重试计数
                finally:
                    # 恢复原始设置
                    self.prefer_direct = old_prefer

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

            # 如果重试都失败并且是使用直接服务器，尝试使用RDAP.org
            elif server_type.startswith('direct_') and self.prefer_direct:
                logger.warning(f"直接查询{domain}失败，尝试使用RDAP.org...")
                # 临时关闭prefer_direct标志
                old_prefer = self.prefer_direct
                self.prefer_direct = False
                try:
                    return self.check_domain(domain, 0)  # 重置重试计数
                finally:
                    # 恢复原始设置
                    self.prefer_direct = old_prefer

        finally:
            # 无论成功失败，都更新最后查询时间
            self.last_query_time[server_type] = time.time()

        return result

    def _check_tld_via_iana(self, tld: str) -> Dict[str, Any]:
        """
        通过IANA RDAP服务检查TLD是否存在和是否支持RDAP

        参数:
            tld: 顶级域名 (例如: '.com')

        返回:
            包含TLD状态信息的字典:
            {
                'exists': TLD是否存在,
                'has_rdap': TLD是否有RDAP服务,
                'status': 状态描述
            }
        """
        # 去掉开头的点
        tld_name = tld[1:] if tld.startswith('.') else tld

        # 构建IANA RDAP URL
        iana_url = RDAP_IANA_URL.format(domain=tld_name)

        result = {
            'exists': False,
            'has_rdap': False,
            'status': 'unknown'
        }

        try:
            # 确保请求间隔
            self._ensure_query_delay('iana')

            # 发送请求
            response = self.session.get(
                iana_url,
                headers=self.headers,
                timeout=self.timeout
            )

            # 更新最后查询时间
            self.last_query_time['iana'] = time.time()

            # 如果状态码为200，表示TLD存在
            if response.status_code == 200:
                result['exists'] = True
                result['status'] = 'exists'

                # 尝试解析响应JSON
                try:
                    data = response.json()

                    # 检查是否包含RDAP服务信息
                    if 'links' in data:
                        for link in data.get('links', []):
                            if link.get('rel') == 'related' and 'rdap' in link.get('href', ''):
                                result['has_rdap'] = True
                                result['status'] = 'has_rdap'
                                break

                except Exception as e:
                    logger.debug(f"解析IANA响应时出错: {e}")

            else:
                result['status'] = 'not_found'

            return result

        except Exception as e:
            logger.debug(f"检查TLD '{tld}'时出错: {e}")
            result['status'] = 'error'
            return result

    def _get_rdap_server_url(self, domain: str, tld: str) -> Tuple[str, str]:
        """
        获取适用于特定域名的RDAP服务器URL

        参数:
            domain: 完整域名
            tld: 顶级域名

        返回:
            元组 (RDAP服务器URL, 服务器类型)
        """
        # 对于已知TLD，根据prefer_direct设置决定使用哪个服务器
        if tld in DIRECT_RDAP_SERVERS:
            if self.prefer_direct:
                return DIRECT_RDAP_SERVERS[tld].format(domain=domain), f'direct_{tld}'

        # 对于其他TLD或当prefer_direct为False时，使用RDAP.org
        return RDAP_ORG_URL.format(domain=domain), 'rdap.org'

    def _is_direct_supported_tld(self, tld: str) -> bool:
        """
        检查TLD是否有直接支持的RDAP服务器

        参数:
            tld: 顶级域名

        返回:
            布尔值，表示是否直接支持
        """
        return tld in DIRECT_RDAP_SERVERS

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

    def _is_valid_domain(self, domain: str) -> bool:
        """
        验证域名格式是否有效

        参数:
            domain: 完整域名

        返回:
            布尔值，表示域名格式是否有效
        """
        # 使用预编译的正则表达式进行验证
        return bool(DOMAIN_REGEX.match(domain))

    def _ensure_query_delay(self, server_type: str) -> None:
        """
        确保对同一服务器的查询有足够的时间间隔
        防止触发RDAP服务器的速率限制

        参数:
            server_type: 服务器类型标识
        """
        if server_type in self.last_query_time:
            last_time = self.last_query_time[server_type]
            now = time.time()
            elapsed = now - last_time

            # 根据服务器类型获取延迟配置
            delay = SERVER_DELAY.get('default', 1.0)  # 默认延迟

            # 检查是否有特定服务器的延迟配置
            if server_type in SERVER_DELAY:
                delay = SERVER_DELAY[server_type]
            # 对于direct_开头的服务器，尝试获取对应TLD的延迟
            elif server_type.startswith('direct_'):
                tld = server_type[7:]  # 去掉'direct_'前缀
                if tld in SERVER_DELAY:
                    delay = SERVER_DELAY[tld]

            if elapsed < delay:
                sleep_time = delay - elapsed
                time.sleep(sleep_time)

    def get_supported_tlds(self) -> List[str]:
        """
        获取已知支持的顶级域名列表
        注意：通过RDAP.org，理论上支持所有注册了RDAP服务的TLD

        返回:
            支持的顶级域名列表
        """
        # 返回直接支持的TLD加上一个通用说明
        direct_tlds = list(DIRECT_RDAP_SERVERS.keys())
        logger.info(f"直接支持的TLD: {', '.join(direct_tlds)}")
        logger.info("通过RDAP.org理论上支持所有注册了RDAP服务的TLD")
        return direct_tlds

    def close(self) -> None:
        """关闭连接会话"""
        if self.session:
            self.session.close()
