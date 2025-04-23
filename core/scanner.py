#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
scanner.py

域名扫描协调器，整合RDAP客户端和域名生成器，
提供完整的域名扫描流程管理、结果处理和统计功能。
"""

import time
import sys
import os
import io
from typing import List, Dict, Any, Optional, Callable, Iterator, Set, TextIO
import logging
from datetime import datetime

# 导入项目其他模块
from .rdap_client import RdapClient
from .generators import DomainGenerator
from .uploader import ResultUploader
from .notifier import Notifier

# 配置日志
logger = logging.getLogger("scanner")


class DomainScanner:
    """域名扫描协调器，管理整个扫描流程"""

    def __init__(self,
                config: Dict[str, Any]):
        """
        初始化域名扫描器

        参数:
            config: 配置字典，包含所有必要设置
        """
        self.tlds = config.get("tlds", [".com", ".org", ".net"])
        self.delay = config.get("delay", 1.0)
        self.max_retries = config.get("max_retries", 2)
        self.hedgedoc_url = config.get("hedgedoc_url", "https://domain.gfw.li")

        # 域名源设置
        self.domain_source = config.get("domain_source", "auto")  # 添加这一行

        # 通知相关配置
        self.notification_method = config.get("notification_method", "none")
        self.notification_config = config.get("notification_config", {})

        # 日志文件和结果文件的固定路径
        self.log_file = "log.txt"
        self.results_file = "results.txt"

        # 生成器相关
        self.domains_file = "domains.txt"
        self.generator_file = "generator_func.py"

        # 内存中存储结果的缓冲区
        self.result_buffer = io.StringIO()

        # 初始化组件
        self.rdap_client = RdapClient(max_retries=self.max_retries)
        self.generator = DomainGenerator()
        self.uploader = ResultUploader(hedgedoc_url=self.hedgedoc_url)
        self.notifier = Notifier(method=self.notification_method, config=self.notification_config)

        # 统计信息
        self.stats = {
            'total_checked': 0,
            'available': 0,
            'registered': 0,
            'errors': 0,
            'rate_limited': 0,
            'start_time': None,
            'end_time': None,
            'tld_stats': {tld: {'checked': 0, 'available': 0} for tld in self.tlds}
        }

        # 检查TLD是否受支持
        self._validate_tlds()

        # 初始化结果缓冲区
        self._initialize_result_buffer()

    def _validate_tlds(self) -> None:
        """验证配置的TLD是否受支持"""
        supported_tlds = self.rdap_client.get_supported_tlds()
        unsupported = [tld for tld in self.tlds if tld not in supported_tlds]

        if unsupported:
            logger.warning(f"以下TLD可能不受支持: {', '.join(unsupported)}")
            logger.warning("这可能导致扫描失败或结果不准确")

    def _initialize_result_buffer(self) -> None:
        """初始化结果缓冲区，添加Markdown头信息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 文档标题
        self.result_buffer.write(f"# 域名可用性扫描结果\n\n")

        # 基本信息部分
        self.result_buffer.write("## 扫描信息\n\n")
        self.result_buffer.write(f"- **扫描时间**: {timestamp}\n")
        self.result_buffer.write(f"- **扫描TLD**: {', '.join(self.tlds)}\n\n")

        # 结果表格标题
        self.result_buffer.write("## 可用域名列表\n\n")

        # Markdown表格头部
        self.result_buffer.write("| 域名 | 状态说明 | 检查时间 |\n")
        self.result_buffer.write("|------|----------|----------|\n")

    def run(self) -> bool:
        """
        运行扫描任务

        返回:
            是否成功完成扫描
        """
        logger.info(f"开始域名扫描任务，TLD列表: {', '.join(self.tlds)}")

        # 重置统计信息
        self._reset_stats()

        try:
            # 确定使用哪种域名源
            domains_generator = None
            domain_source = getattr(self, "domain_source", "auto")  # 从实例属性获取

            # 根据配置选择域名源
            if domain_source == "file" and os.path.exists(self.domains_file):
                logger.info(f"从文件加载域名: {self.domains_file}")
                domains_generator = self.generator.from_file(self.domains_file)

            elif domain_source == "generator" and os.path.exists(self.generator_file):
                logger.info(f"从生成器文件加载域名: {self.generator_file}")
                domains_generator = self.generator.from_function(generator_file=self.generator_file)

            elif domain_source == "auto":
                # 自动模式下，检查两个文件的存在情况
                if os.path.exists(self.domains_file):
                    logger.info(f"自动模式: 从文件加载域名: {self.domains_file}")
                    domains_generator = self.generator.from_file(self.domains_file)
                elif os.path.exists(self.generator_file):
                    logger.info(f"自动模式: 从生成器文件加载域名: {self.generator_file}")
                    domains_generator = self.generator.from_function(generator_file=self.generator_file)
                else:
                    error_msg = f"未找到域名源文件。请提供 {self.domains_file} 或 {self.generator_file}"
                    logger.error(error_msg)
                    return False

            else:
                error_msg = f"未找到有效的域名源。请检查配置和文件是否存在"
                logger.error(error_msg)
                return False

            # 执行扫描
            self._scan_domains(domains_generator)

            # 完成扫描
            return True

        except KeyboardInterrupt:
            logger.warning("用户中断扫描 (Ctrl+C)")
            self._finalize_scan(interrupted=True)
            return False
        except Exception as e:
            logger.error(f"扫描过程中发生错误: {e}", exc_info=True)
            self._finalize_scan(error=str(e))
            return False
        finally:
            # 无论如何都确保资源被正确关闭
            self.close()

    def _scan_domains(self, domains_generator: Iterator[str]) -> None:
        """
        扫描给定的域名生成器中的所有域名

        参数:
            domains_generator: 域名生成器
        """
        self.stats['start_time'] = time.time()

        # 记录上次打印进度的时间
        last_progress_time = time.time()
        progress_interval = 5  # 进度更新间隔(秒)

        # 扫描每个域名基础部分
        for domain_base in domains_generator:
            for tld in self.tlds:
                full_domain = f"{domain_base}{tld}"

                # 检查域名可用性
                result = self.rdap_client.check_domain(full_domain)

                # 更新统计信息
                self._update_stats(result)

                # 记录结果
                self._log_result(result)

                # 如果域名可用，保存到结果缓冲区
                if result['available']:
                    self._save_result(result)

                # 查询间隔
                if self.delay > 0:
                    time.sleep(self.delay)

            # 定期更新进度
            current_time = time.time()
            if current_time - last_progress_time >= progress_interval:
                self._log_progress()
                last_progress_time = current_time

        # 扫描完成，处理结果
        self._finalize_scan()

    def _update_stats(self, result: Dict[str, Any]) -> None:
        """
        更新扫描统计信息

        参数:
            result: 域名查询结果
        """
        # 更新总计数
        self.stats['total_checked'] += 1

        # 更新状态计数
        status = result['status']
        if result['available']:
            self.stats['available'] += 1
        elif status == 'registered':
            self.stats['registered'] += 1
        elif status == 'rate_limited':
            self.stats['rate_limited'] += 1
        else:
            self.stats['errors'] += 1

        # 更新TLD统计
        tld = result['tld']
        if tld in self.stats['tld_stats']:
            self.stats['tld_stats'][tld]['checked'] += 1
            if result['available']:
                self.stats['tld_stats'][tld]['available'] += 1

    def _log_result(self, result: Dict[str, Any]) -> None:
        """
        记录域名查询结果到日志

        参数:
            result: 域名查询结果
        """
        domain = result['domain']
        status = result['status']
        status_cn = result['status_cn']

        # 创建日志消息
        log_message = f"[{self.stats['total_checked']}] {domain} - {status_cn}"
        if 'error' in result and result['error']:
            log_message += f" - {result['error']}"

        # 根据结果状态记录到不同级别的日志
        if result['available']:
            logger.info(f"发现可用域名: {log_message}")
        elif status == 'rate_limited':
            logger.warning(log_message)
        elif 'error' in result and result['error']:
            logger.error(log_message)
        else:
            logger.debug(log_message)  # 使用debug级别避免日志过于冗长

    def _save_result(self, result: Dict[str, Any]) -> None:
        """
        将可用域名保存到结果缓冲区，使用Markdown表格行格式

        参数:
            result: 域名查询结果
        """
        if result['available']:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 使用Markdown表格行格式
            self.result_buffer.write(f"| {result['domain']} | {result['status_cn']} | {timestamp} |\n")

    def _log_progress(self) -> None:
        """记录当前扫描进度到日志"""
        if self.stats['total_checked'] == 0:
            return

        elapsed = time.time() - self.stats['start_time']
        rate = self.stats['total_checked'] / elapsed if elapsed > 0 else 0

        progress_info = [
            f"--- 扫描进度 ---",
            f"已检查: {self.stats['total_checked']} 个域名",
            f"可用域名: {self.stats['available']}",
            f"已注册: {self.stats['registered']}",
            f"错误: {self.stats['errors']}",
            f"速率限制: {self.stats['rate_limited']}",
            f"耗时: {elapsed:.1f} 秒",
            f"速度: {rate:.2f} 个域名/秒",
            "----------------"
        ]

        # 记录到日志
        logger.info("扫描进度统计：")
        for line in progress_info:
            logger.info(line)

    def _finalize_scan(self, interrupted: bool = False, error: Optional[str] = None) -> None:
        """
        完成扫描，处理结果，生成统计信息并上传

        参数:
            interrupted: 是否被用户中断
            error: 错误信息(如有)
        """
        self.stats['end_time'] = time.time()

        # 计算统计信息
        duration = self.stats['end_time'] - self.stats['start_time']
        rate = self.stats['total_checked'] / duration if duration > 0 else 0

        # 根据状态记录日志
        if interrupted:
            logger.warning("扫描已中断")
        elif error:
            logger.error(f"扫描失败: {error}")
        else:
            logger.info("扫描完成")

        # 添加统计信息到结果缓冲区
        self._write_summary_to_buffer()

        # 上传结果并获取URL
        result_url = self._upload_and_get_url()

        # 如果获取到URL，保存到结果文件
        if result_url:
            self._save_url_to_results_file(result_url)

            # 发送通知
            self._send_completion_notification(result_url, interrupted, error)

    def _write_summary_to_buffer(self) -> None:
        """将扫描统计信息以Markdown格式写入结果缓冲区"""
        try:
            # 计算统计数据
            end_time = datetime.fromtimestamp(self.stats['end_time']).strftime("%Y-%m-%d %H:%M:%S")
            duration = self.stats['end_time'] - self.stats['start_time']

            # 添加统计部分标题
            self.result_buffer.write("\n## 扫描统计\n\n")

            # 基本统计信息
            self.result_buffer.write("### 基本统计\n\n")
            self.result_buffer.write(f"- **扫描结束时间**: {end_time}\n")
            self.result_buffer.write(f"- **总检查域名数**: {self.stats['total_checked']}\n")
            self.result_buffer.write(f"- **发现可用域名**: {self.stats['available']}\n")
            self.result_buffer.write(f"- **总耗时**: {duration:.1f} 秒\n")

            # TLD统计信息表格
            self.result_buffer.write("\n### TLD统计\n\n")
            self.result_buffer.write("| TLD | 检查数量 | 可用数量 | 可用率 |\n")
            self.result_buffer.write("|-----|----------|----------|-------|\n")

            for tld in self.tlds:
                stats = self.stats['tld_stats'][tld]
                available_count = stats['available']
                checked_count = stats['checked']

                if checked_count > 0:
                    available_percent = (available_count / checked_count) * 100
                    self.result_buffer.write(f"| {tld} | {checked_count} | {available_count} | {available_percent:.1f}% |\n")
                else:
                    self.result_buffer.write(f"| {tld} | 0 | 0 | 0.0% |\n")

            # 添加简短的结束说明
            self.result_buffer.write("\n---\n")
            self.result_buffer.write(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

        except Exception as e:
            logger.error(f"写入统计信息到缓冲区时出错: {e}", exc_info=True)

    def _upload_and_get_url(self) -> Optional[str]:
        """
        上传扫描结果并获取URL

        返回:
            结果URL或None（如果上传失败）
        """
        try:
            # 获取缓冲区内容
            markdown_content = self.result_buffer.getvalue()

            # 如果没有可用域名，添加提示信息
            if self.stats['available'] == 0:
                markdown_content += "\n\n> 注意：本次扫描未发现可用域名。\n"

            # 生成标题，包含时间和TLD信息
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            title = f"域名扫描结果 - {timestamp} - {','.join(self.tlds)}"

            # 上传内容
            logger.info("正在上传扫描结果...")
            success, message, url = self.uploader.upload_markdown_content(markdown_content, title)

            if success and url:
                logger.info(f"扫描结果已上传，URL: {url}")
                return url
            else:
                logger.error(f"上传结果失败: {message}")
                return None
        except Exception as e:
            logger.error(f"上传结果时发生错误: {e}", exc_info=True)
            return None

    def _save_url_to_results_file(self, url: str) -> None:
        """
        将结果URL保存到results.txt文件中

        参数:
            url: 结果URL
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tlds_str = ', '.join(self.tlds)
            url_entry = f"[{timestamp}] TLDs: {tlds_str} - {url}\n"

            # 追加到结果文件
            with open(self.results_file, 'a', encoding='utf-8') as f:
                f.write(url_entry)

            logger.info(f"结果URL已保存到: {self.results_file}")
        except Exception as e:
            logger.error(f"保存URL到结果文件时出错: {e}", exc_info=True)

    def _send_completion_notification(self, url: str, interrupted: bool = False, error: Optional[str] = None) -> None:
        """
        发送完成通知

        参数:
            url: 结果URL
            interrupted: 是否被中断
            error: 错误信息(如有)
        """
        if self.notification_method == "none":
            return

        try:
            # 准备通知内容
            if interrupted:
                subject = "域名扫描已中断"
                message = f"域名扫描任务已被中断。\n\n扫描统计:\n- 已检查: {self.stats['total_checked']}\n- 可用域名: {self.stats['available']}"
            elif error:
                subject = "域名扫描失败"
                message = f"域名扫描任务失败: {error}\n\n扫描统计:\n- 已检查: {self.stats['total_checked']}\n- 可用域名: {self.stats['available']}"
            else:
                subject = "域名扫描完成"
                message = f"域名扫描任务已成功完成。\n\n扫描统计:\n- 已检查: {self.stats['total_checked']}\n- 可用域名: {self.stats['available']}\n- TLD: {', '.join(self.tlds)}"

            # 发送通知
            logger.info(f"正在发送{self.notification_method}通知...")
            success = self.notifier.send_notification(subject, message, url)

            if success:
                logger.info("通知发送成功")
            else:
                logger.warning("通知发送失败")
        except Exception as e:
            logger.error(f"发送通知时出错: {e}", exc_info=True)

    def _reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = {
            'total_checked': 0,
            'available': 0,
            'registered': 0,
            'errors': 0,
            'rate_limited': 0,
            'start_time': None,
            'end_time': None,
            'tld_stats': {tld: {'checked': 0, 'available': 0} for tld in self.tlds}
        }

        # 重置结果缓冲区
        self.result_buffer = io.StringIO()
        self._initialize_result_buffer()

    def close(self) -> None:
        """关闭资源"""
        # 关闭RDAP客户端
        if hasattr(self, 'rdap_client') and self.rdap_client:
            try:
                self.rdap_client.close()
            except Exception:
                pass

        # 关闭结果缓冲区
        if hasattr(self, 'result_buffer') and self.result_buffer:
            try:
                self.result_buffer.close()
            except Exception:
                pass
