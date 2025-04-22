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
from typing import List, Dict, Any, Optional, Callable, Iterator, Set, TextIO
import logging
from datetime import datetime

# 导入项目其他模块
from .rdap_client import RdapClient
from .generators import DomainGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("scanner")


class DomainScanner:
    """域名扫描协调器，管理整个扫描流程"""

    def __init__(self,
                tlds: List[str],
                output_file: Optional[str],  # 修改为可选参数
                delay: float = 1.0,
                max_retries: int = 2,
                verbose: bool = False):
        """
        初始化域名扫描器

        参数:
            tlds: 待扫描的顶级域名列表 ['.com', '.org', '.net']
            output_file: 结果输出文件路径，None表示不保存到文件
            delay: 查询间隔(秒)
            max_retries: 重试次数
            verbose: 是否输出详细信息
        """
        self.tlds = tlds
        self.output_file = output_file
        self.delay = delay
        self.max_retries = max_retries
        self.verbose = verbose

        # 输出文件句柄
        self.output_handle = None

        # 初始化组件
        self.rdap_client = RdapClient(max_retries=max_retries)
        self.generator = DomainGenerator()

        # 统计信息
        self.stats = {
            'total_checked': 0,
            'available': 0,
            'registered': 0,
            'errors': 0,
            'rate_limited': 0,
            'start_time': None,
            'end_time': None,
            'tld_stats': {tld: {'checked': 0, 'available': 0} for tld in tlds}
        }

        # 检查TLD是否受支持
        self._validate_tlds()

        # 打开输出文件（如果需要）
        if self.output_file:
            self._open_output_file()

    def _validate_tlds(self) -> None:
        """验证配置的TLD是否受支持"""
        supported_tlds = self.rdap_client.get_supported_tlds()
        unsupported = [tld for tld in self.tlds if tld not in supported_tlds]

        if unsupported:
            logger.warning(f"以下TLD可能不受支持: {', '.join(unsupported)}")
            logger.warning("这可能导致扫描失败或结果不准确")

    def _open_output_file(self) -> None:
        """打开输出文件，处理可能的错误"""
        if not self.output_file:
            return  # 如果不需要输出文件，直接返回

        try:
            self.output_handle = open(self.output_file, 'w', encoding='utf-8')
            # 写入文件头
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.output_handle.write(f"# 域名可用性扫描结果 - {timestamp}\n")
            self.output_handle.write(f"# 扫描TLD: {', '.join(self.tlds)}\n")

            # 更新格式说明
            self.output_handle.write("# 格式: 域名 | 状态 | 中文状态 | 检查时间\n")

            # 添加表头和分隔线，增强可读性
            self.output_handle.write("\n")
            self.output_handle.write(f"{'域名':<30} | {'状态':<15} | {'中文状态':<15} | 检查时间\n")
            self.output_handle.write("-" * 30 + "-+-" + "-" * 15 + "-+-" + "-" * 15 + "-+-" + "-" * 19 + "\n")
            self.output_handle.flush()
        except IOError as e:
            logger.error(f"无法打开输出文件 '{self.output_file}': {e}")
            raise

    def scan_from_file(self, filepath: str) -> None:
        """
        从文件加载域名并进行扫描

        参数:
            filepath: 域名文件路径
        """
        logger.info(f"开始从文件 '{filepath}' 扫描域名...")
        logger.info(f"TLD列表: {', '.join(self.tlds)}")
        logger.info(f"查询间隔: {self.delay}秒, 最大重试: {self.max_retries}次")

        # 重置统计信息
        self._reset_stats()

        try:
            # 从文件生成域名
            domains_generator = self.generator.from_file(filepath)

            # 执行扫描
            self._scan_domains(domains_generator)

        except KeyboardInterrupt:
            logger.warning("用户中断扫描 (Ctrl+C)")
            self._finalize_scan(interrupted=True)
        except Exception as e:
            logger.error(f"扫描过程中发生错误: {e}", exc_info=True)
            self._finalize_scan(error=str(e))
        else:
            self._finalize_scan()

    def scan_from_function(self, generator_func: Optional[Callable[[], Iterator[str]]] = None,
                         generator_file: Optional[str] = None) -> None:
        """
        使用自定义函数生成域名并进行扫描

        参数:
            generator_func: 直接传递的生成器函数
            generator_file: 包含生成器函数的Python文件路径
        """
        source = generator_file if generator_file else "自定义函数"
        logger.info(f"开始使用 {source} 扫描域名...")
        logger.info(f"TLD列表: {', '.join(self.tlds)}")
        logger.info(f"查询间隔: {self.delay}秒, 最大重试: {self.max_retries}次")

        # 重置统计信息
        self._reset_stats()

        try:
            # 从函数生成域名
            domains_generator = self.generator.from_function(
                generator_func=generator_func,
                generator_file=generator_file
            )

            # 执行扫描
            self._scan_domains(domains_generator)

        except KeyboardInterrupt:
            logger.warning("用户中断扫描 (Ctrl+C)")
            self._finalize_scan(interrupted=True)
        except Exception as e:
            logger.error(f"扫描过程中发生错误: {e}", exc_info=True)
            self._finalize_scan(error=str(e))
        else:
            self._finalize_scan()

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

                # 输出详细信息
                self._print_result(result)

                # 如果域名可用，保存到结果文件
                if result['available']:
                    self._save_result(result)

                # 查询间隔
                if self.delay > 0:
                    time.sleep(self.delay)

            # 定期更新进度
            current_time = time.time()
            if current_time - last_progress_time >= progress_interval:
                self._print_progress()
                last_progress_time = current_time

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

    def _print_result(self, result: Dict[str, Any]) -> None:
        """
        打印域名查询结果

        参数:
            result: 域名查询结果
        """
        domain = result['domain']
        status = result['status']
        status_cn = result['status_cn']

        # 详细模式下打印所有结果，否则只打印可用域名
        if self.verbose or result['available']:
            if result['available']:
                # 可用域名使用绿色显示
                print(f"[{self.stats['total_checked']}] \033[92m{domain}\033[0m - {status_cn}")
            elif status == 'rate_limited':
                # 速率限制使用黄色显示
                print(f"[{self.stats['total_checked']}] {domain} - \033[93m{status_cn}\033[0m")
            elif 'error' in result and result['error']:
                # 错误使用红色显示
                print(f"[{self.stats['total_checked']}] {domain} - \033[91m{status_cn}\033[0m - {result['error']}")
            else:
                # 其他状态正常显示
                print(f"[{self.stats['total_checked']}] {domain} - {status_cn}")

    def _save_result(self, result: Dict[str, Any]) -> None:
        """
        保存可用域名到结果文件

        参数:
            result: 域名查询结果
        """
        if self.output_handle and result['available']:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 使用固定宽度的列格式，提高可读性
            domain_str = f"{result['domain']:<30}"  # 域名左对齐，宽度30
            status_str = f"{result['status']:<15}"  # 状态左对齐，宽度15
            status_cn_str = f"{result['status_cn']:<15}"  # 中文状态左对齐，宽度15

            # 添加分隔符，使行更易读
            line = f"{domain_str} | {status_str} | {status_cn_str} | {timestamp}\n"
            self.output_handle.write(line)
            self.output_handle.flush()  # 立即写入

    def _print_progress(self) -> None:
        """打印当前扫描进度"""
        if self.stats['total_checked'] == 0:
            return

        elapsed = time.time() - self.stats['start_time']
        rate = self.stats['total_checked'] / elapsed if elapsed > 0 else 0

        print(f"\n--- 扫描进度 ---")
        print(f"已检查: {self.stats['total_checked']} 个域名")
        print(f"可用域名: {self.stats['available']}")
        print(f"已注册: {self.stats['registered']}")
        print(f"错误: {self.stats['errors']}")
        print(f"速率限制: {self.stats['rate_limited']}")
        print(f"耗时: {elapsed:.1f} 秒")
        print(f"速度: {rate:.2f} 个域名/秒")
        print("----------------\n")

    def _finalize_scan(self, interrupted: bool = False, error: Optional[str] = None) -> None:
        """
        完成扫描，输出最终统计信息

        参数:
            interrupted: 是否被用户中断
            error: 错误信息(如有)
        """
        self.stats['end_time'] = time.time()

        # 计算一些附加统计信息
        duration = self.stats['end_time'] - self.stats['start_time']
        rate = self.stats['total_checked'] / duration if duration > 0 else 0

        # 打印分隔线
        print("\n" + "=" * 50)

        # 打印状态标题
        if interrupted:
            print("\n\033[93m扫描已中断\033[0m")
        elif error:
            print(f"\n\033[91m扫描失败: {error}\033[0m")
        else:
            print("\n\033[92m扫描完成\033[0m")

        # 打印统计信息
        print("\n--- 扫描统计 ---")
        print(f"总检查域名数: {self.stats['total_checked']}")
        print(f"可用域名数: \033[92m{self.stats['available']}\033[0m")
        print(f"已注册域名数: {self.stats['registered']}")
        print(f"错误数: {self.stats['errors']}")
        print(f"速率限制次数: {self.stats['rate_limited']}")
        print(f"总耗时: {duration:.1f} 秒")
        print(f"平均速度: {rate:.2f} 个域名/秒")

        # 打印TLD统计
        print("\n--- TLD统计 ---")
        for tld in self.tlds:
            stats = self.stats['tld_stats'][tld]
            available_count = stats['available']
            checked_count = stats['checked']
            if checked_count > 0:
                available_percent = (available_count / checked_count) * 100
                print(f"{tld}: 检查 {checked_count}, 可用 {available_count} ({available_percent:.1f}%)")
            else:
                print(f"{tld}: 检查 0, 可用 0 (0.0%)")

        # 写入总结到结果文件
        if self.output_handle:
            self._write_summary_to_file()

        print("\n" + "=" * 50)

    def _write_summary_to_file(self) -> None:
        """将扫描统计信息写入结果文件"""
        if not self.output_handle:
            return  # 如果没有输出文件，直接返回

        try:
            self.output_handle.write("\n\n# --- 扫描统计 ---\n")

            # 基本统计
            end_time = datetime.fromtimestamp(self.stats['end_time']).strftime("%Y-%m-%d %H:%M:%S")
            duration = self.stats['end_time'] - self.stats['start_time']

            self.output_handle.write(f"# 扫描结束时间: {end_time}\n")
            self.output_handle.write(f"# 总检查域名数: {self.stats['total_checked']}\n")
            self.output_handle.write(f"# 可用域名数: {self.stats['available']}\n")
            self.output_handle.write(f"# 总耗时: {duration:.1f} 秒\n")

            # TLD统计
            self.output_handle.write("\n# --- TLD统计 ---\n")
            for tld in self.tlds:
                stats = self.stats['tld_stats'][tld]
                self.output_handle.write(f"# {tld}: 检查 {stats['checked']}, 可用 {stats['available']}\n")

            self.output_handle.flush()
        except Exception as e:
            logger.error(f"写入统计信息到文件时出错: {e}")

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

    def close(self) -> None:
        """关闭资源"""
        # 关闭RDAP客户端
        if hasattr(self, 'rdap_client') and self.rdap_client:
            self.rdap_client.close()

        # 关闭输出文件
        if hasattr(self, 'output_handle') and self.output_handle:
            try:
                self.output_handle.close()
            except Exception:
                pass


# 当作为独立脚本运行时的测试代码
if __name__ == "__main__":
    # 简单的测试函数
    def test_scanner():
        print("这个模块需要与其他模块一起使用，请通过主程序调用。")
