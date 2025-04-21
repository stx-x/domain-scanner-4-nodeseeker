#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
cli.py

命令行接口模块，负责解析命令行参数、验证用户输入，
并调用域名扫描器执行扫描任务。
"""

import sys
import argparse
import os
import logging
from typing import Dict, Any, List, Optional

# 导入项目其他模块
from core.scanner import DomainScanner

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("cli")

# 程序版本和描述
PROGRAM_NAME = "Domain Availability Scanner"
VERSION = "1.0.0"
DESCRIPTION = "基于RDAP协议的域名可用性扫描工具"


def parse_arguments() -> argparse.Namespace:
    """
    解析命令行参数

    返回:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description=f"{PROGRAM_NAME} v{VERSION} - {DESCRIPTION}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # 必需参数
    parser.add_argument("-t", "--tlds", nargs="+", required=True,
                        help="要检查的顶级域名列表 (例如: .com .org .net)")
    parser.add_argument("-o", "--output", type=str, required=True,
                        help="输出结果文件")

    # 域名来源 (必须指定其中一个)
    source_group = parser.add_argument_group("域名来源 (必须指定其中一个)")
    source_exclusive = source_group.add_mutually_exclusive_group(required=True)
    source_exclusive.add_argument("-f", "--file", type=str,
                                 help="从文件读取域名列表")
    source_exclusive.add_argument("-g", "--generator-file", type=str,
                                 help="使用自定义生成器函数文件")

    # 可选参数
    parser.add_argument("-d", "--delay", type=float, default=1.0,
                        help="查询间隔(秒)")
    parser.add_argument("-r", "--max-retries", type=int, default=2,
                        help="最大重试次数")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="详细输出模式")
    parser.add_argument("--version", action="version",
                        version=f"{PROGRAM_NAME} v{VERSION}")

    args = parser.parse_args()

    return args


def validate_arguments(args: argparse.Namespace) -> Optional[str]:
    """
    验证参数是否有效

    参数:
        args: 解析后的参数对象

    返回:
        错误消息 (如果有错误) 或 None (如果验证通过)
    """
    # 检查TLD格式
    for tld in args.tlds:
        if not tld.startswith('.'):
            return f"无效的TLD格式: {tld}，应以'.'开头 (例如: .com)"
        if len(tld) < 2 or not all(c.isalnum() or c == '.' for c in tld):
            return f"无效的TLD格式: {tld}"

    # 检查文件存在性
    if args.file and not os.path.exists(args.file):
        return f"找不到域名文件: {args.file}"

    if args.generator_file and not os.path.exists(args.generator_file):
        return f"找不到生成器文件: {args.generator_file}"

    # 检查延迟值
    if args.delay < 0:
        return "延迟值不能为负数"
    elif args.delay < 0.1:
        logger.warning("警告: 延迟值过低 (< 0.1秒) 可能导致速率限制")

    # 检查重试次数
    if args.max_retries < 0:
        return "最大重试次数不能为负数"

    # 检查输出文件目录是否存在
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        return f"输出文件目录不存在: {output_dir}"

    # 检查是否能写入输出文件
    try:
        # 尝试创建或打开文件
        with open(args.output, 'a'):
            pass
    except IOError as e:
        return f"无法写入输出文件 '{args.output}': {e}"

    return None  # 验证通过


def print_banner() -> None:
    """打印程序横幅"""
    banner = f"""
    ┌─────────────────────────────────────────┐
    │                                         │
    │   {PROGRAM_NAME}  v{VERSION}   │
    │   {DESCRIPTION}      │
    │                                         │
    └─────────────────────────────────────────┘
    """
    print(banner)


def print_config_summary(args: argparse.Namespace) -> None:
    """
    打印配置摘要

    参数:
        args: 解析后的参数对象
    """
    print("\n=== 扫描配置 ===")
    print(f"TLD列表: {', '.join(args.tlds)}")

    if args.file:
        print(f"域名来源: 文件 '{args.file}'")
    elif args.generator_file:
        print(f"域名来源: 自定义生成器 '{args.generator_file}'")

    print(f"输出文件: {args.output}")
    print(f"查询间隔: {args.delay} 秒")
    print(f"最大重试: {args.max_retries} 次")
    print(f"详细模式: {'开启' if args.verbose else '关闭'}")
    print("===============\n")


def run_scanner(args: argparse.Namespace) -> int:
    """
    运行域名扫描器

    参数:
        args: 解析后的参数对象

    返回:
        退出代码 (0表示成功，非0表示错误)
    """
    try:
        # 初始化扫描器
        scanner = DomainScanner(
            tlds=args.tlds,
            output_file=args.output,
            delay=args.delay,
            max_retries=args.max_retries,
            verbose=args.verbose
        )

        # 根据域名来源运行扫描
        try:
            if args.file:
                scanner.scan_from_file(args.file)
            elif args.generator_file:
                scanner.scan_from_function(generator_file=args.generator_file)
        finally:
            # 确保资源被正确关闭
            scanner.close()

    except KeyboardInterrupt:
        print("\n程序被用户中断 (Ctrl+C)")
        return 1
    except Exception as e:
        logger.error(f"扫描过程中出现错误: {e}", exc_info=True)
        print(f"\n扫描失败: {e}")
        return 1

    return 0


def main() -> int:
    """
    主程序入口点

    返回:
        退出代码 (0表示成功，非0表示错误)
    """
    # 打印程序横幅
    print_banner()

    try:
        # 解析命令行参数
        args = parse_arguments()

        # 验证参数
        error = validate_arguments(args)
        if error:
            print(f"错误: {error}")
            return 1

        # 打印配置摘要
        print_config_summary(args)

        # 运行扫描器
        return run_scanner(args)

    except Exception as e:
        logger.error(f"未预期的错误: {e}", exc_info=True)
        print(f"发生未预期的错误: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
