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
import datetime
from typing import Dict, Any, List, Optional

# 导入项目其他模块
from .scanner import DomainScanner

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("cli")

# 程序版本和描述
PROGRAM_NAME = "Domain Availability Scanner"
VERSION = "0.1.1"
DESCRIPTION = "基于RDAP协议的域名可用性扫描工具"

class ChineseArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # 常见错误消息的中文替换
        message = message.replace("the following arguments are required:", "缺少以下必需参数:")
        message = message.replace("expected one argument", "此选项需要一个参数值")
        message = message.replace("unrecognized arguments", "无法识别的参数")
        message = message.replace("not allowed with argument", "不能与参数一起使用")
        message = message.replace("argument -", "参数 -")
        message = message.replace("one of the arguments", "以下参数之一")
        message = message.replace("is required", "是必需的")
        message = message.replace("must be specified", "必须指定")

        self.exit(2, f"错误: {message}\n")

    def print_help(self, file=None):
        super().print_help(file)

    def print_usage(self, file=None):
        super().print_usage(file)

def parse_arguments() -> argparse.Namespace:
    """
    解析命令行参数

    返回:
        解析后的参数对象
    """
    parser = ChineseArgumentParser(
        description=f"{PROGRAM_NAME} v{VERSION} - {DESCRIPTION}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # 必需参数
    parser.add_argument("-t", "--tlds", nargs="+", required=True,
                        help="要检查的顶级域名列表 (例如: .com .org .net)")

    # 域名来源 (必须指定其中一个)
    source_group = parser.add_argument_group("域名来源 (必须指定其中一个)")
    source_exclusive = source_group.add_mutually_exclusive_group(required=True)
    source_exclusive.add_argument("-f", "--file", type=str,
                                 help="从文件读取域名列表")
    source_exclusive.add_argument("-g", "--generator-file", type=str,
                                 help="使用自定义生成器函数文件")

    # 可选参数
    parser.add_argument("-o", "--output", type=str, required=False,
                        help="输出结果文件")
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

def confirm_prompt(question: str, default: str = "y") -> bool:
    """
    向用户询问是否确认操作

    参数:
        question: 问题文本
        default: 默认回答 ('y' 或 'n')

    返回:
        True 表示用户确认，False 表示用户拒绝
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}

    if default == "y":
        prompt = " [Y/n] "
    elif default == "n":
        prompt = " [y/N] "
    else:
        prompt = " [y/n] "

    while True:
        print(question + prompt, end="")
        choice = input().lower()

        if choice == "":
            return True if default == "y" else False
        elif choice in valid:
            return valid[choice]
        else:
            print("请输入 'yes' 或 'no' (或 'y' 或 'n')")

def validate_arguments(args: argparse.Namespace) -> Optional[str]:
    """
    验证参数是否有效，并处理确认逻辑

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

    # 处理输出文件逻辑
    if not args.output:
        # 用户未提供输出文件路径，询问选项
        print("\n输出选项:")
        print("1. 使用默认输出文件")
        print("2. 不保存结果到文件（仅在控制台显示）")
        print("3. 手动指定输出文件")

        while True:
            choice = input("\n请选择 [1/2/3]: ").strip()

            if choice == '1':
                result_dir = os.path.join(os.getcwd(), "result")
                if not os.path.exists(result_dir):
                    try:
                        os.makedirs(result_dir)
                    except OSError as e:
                        return f"无法创建result目录: {e}"
                current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                default_output = os.path.join(result_dir, f"domain_scan_results_{current_time}.md")
                print(f"将使用默认输出文件: '{default_output}'")
                args.output = default_output
                break
            elif choice == '2':
                print("不保存结果到文件，仅在控制台显示")
                args.output = None  # 显式设置为None表示不使用输出文件
                return None  # 验证通过，直接返回
            elif choice == '3':
                new_output = input("请输入输出文件路径: ").strip()
                if new_output:
                    args.output = new_output
                    break
                else:
                    print("输入无效，请重新选择")
            else:
                print("选择无效，请输入1、2或3")

    # 如果用户选择了输出文件（不是选项2），继续检查文件和目录
    if args.output is not None:
        # 检查输出文件是否已存在
        if os.path.exists(args.output):
            if not confirm_prompt(f"警告: 输出文件 '{args.output}' 已存在，继续操作将覆盖现有内容。是否继续?", default="n"):
                return "用户取消操作：不覆盖现有文件"

        # 检查输出文件目录是否存在
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            if confirm_prompt(f"输出目录 '{output_dir}' 不存在。是否创建?"):
                try:
                    os.makedirs(output_dir)
                except OSError as e:
                    return f"无法创建输出目录 '{output_dir}': {e}"
            else:
                return "用户取消操作：不创建输出目录"

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

    if args.output:
        print(f"输出文件: {args.output}")
    else:
        print("输出文件: 不保存结果到文件（仅在控制台显示）")

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
            output_file=args.output,  # 如果为None，则不保存到文件
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
