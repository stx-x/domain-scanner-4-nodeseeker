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
from datetime import datetime
import daemon
import lockfile
import signal
import time

from typing import Dict, Any, List, Optional

from wcwidth import wcswidth

# 导入项目其他模块
from .scanner import DomainScanner
from .config_parser import ConfigParser

# 程序版本和描述
PROGRAM_NAME = "Domain Seeker"
VERSION = "0.2.0"
DESCRIPTION = "基于RDAP协议的域名可用性扫描工具"

class ChineseArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # 简化错误消息的中文替换
        message = message.replace("the following arguments are required:", "缺少以下必需参数:")
        message = message.replace("unrecognized arguments", "无法识别的参数")
        self.exit(2, f"错误: {message}\n")

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

    # 仅保留版本和详细输出选项
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="详细输出模式")
    parser.add_argument("--version", action="version",
                        version=f"{PROGRAM_NAME} v{VERSION}")

    return parser.parse_args()

def print_banner() -> None:
    """打印程序横幅 (已修正中文字符对齐)"""

    # 1. 准备文本
    program_text = f"{PROGRAM_NAME}  v{VERSION}"
    desc_text = f"{DESCRIPTION}"

    # 2. 定义框内视觉宽度 (不包括左右的 '│')
    # '┌─────────────────────────────────────────┐' 包含 41 个 '-'
    # '│                                         │' 包含 41 个空格
    inner_width = 41

    # 3. 定义行内固定前缀及其视觉宽度
    # "│   " -> 左边框 + 3个空格
    left_padding_str = "   "
    left_padding_width = 3 # 3 个空格宽度

    # 4. 计算文本的视觉宽度 (使用 wcswidth)
    # wcswidth 会正确处理中文字符（通常算作宽度2）和英文字符（宽度1）
    program_text_width = wcswidth(program_text)
    desc_text_width = wcswidth(desc_text)

    # 处理 wcswidth 可能返回 -1 的情况 (例如包含无法打印的控制字符)
    # 在这种简单场景下，如果为负，可以回退到 len (不精确) 或视为0，或报错
    # 这里我们简单处理，如果为负，可能导致对齐错误，但避免程序崩溃
    if program_text_width < 0:
        print(f"警告: 无法计算 program_text '{program_text}' 的显示宽度，可能包含控制字符。")
        program_text_width = len(program_text) # 回退策略 (可能不准)
    if desc_text_width < 0:
        print(f"警告: 无法计算 desc_text '{desc_text}' 的显示宽度，可能包含控制字符。")
        desc_text_width = len(desc_text)     # 回退策略 (可能不准)


    # 5. 计算需要填充的空格数量
    # 填充空格数 = 总内部宽度 - 左侧固定空格宽度 - 文本视觉宽度
    program_padding_count = inner_width - left_padding_width - program_text_width
    desc_padding_count = inner_width - left_padding_width - desc_text_width

    # 确保填充数不为负 (如果文本+左填充超过了内部宽度)
    program_padding_count = max(0, program_padding_count)
    desc_padding_count = max(0, desc_padding_count)

    # 创建填充字符串
    program_padding = " " * program_padding_count
    desc_padding = " " * desc_padding_count

    # 6. 构建 Banner 字符串
    # 注意 f-string 中变量的引用
    banner = f"""
    ┌─────────────────────────────────────────┐
    │                                         │
    │{left_padding_str}{program_text}{program_padding}│
    │{left_padding_str}{desc_text}{desc_padding}│
    │                                         │
    └─────────────────────────────────────────┘
    """
    # 7. 打印 Banner
    print(banner)

def setup_logging(verbose: bool = False) -> None:
    """
    设置日志记录

    参数:
        verbose: 是否启用详细日志
    """
    # 清除现有的日志处理器
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # 设置日志级别
    log_level = logging.DEBUG if verbose else logging.INFO

    # 创建文件处理器，固定文件名为log.txt
    file_handler = logging.FileHandler(filename="log.txt", mode="w", encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    # 配置根日志记录器
    logging.root.setLevel(log_level)
    logging.root.addHandler(file_handler)
    logging.root.addHandler(console_handler)

    # 记录初始日志
    logging.info(f"{PROGRAM_NAME} v{VERSION} 启动")
    logging.info(f"日志级别: {'DEBUG' if verbose else 'INFO'}")

def run_scanner(config: Dict[str, Any], verbose: bool) -> int:
    """
    运行域名扫描器

    参数:
        config: 配置字典
        verbose: 是否详细输出模式

    返回:
        退出代码 (0表示成功，非0表示错误)
    """
    try:
        # 初始化扫描器
        scanner = DomainScanner(config=config)

        # 运行扫描
        success = scanner.run()

        return 0 if success else 1

    except KeyboardInterrupt:
        logging.warning("程序被用户中断 (Ctrl+C)")
        return 1
    except Exception as e:
        logging.error(f"扫描过程中出现错误: {e}", exc_info=True)
        return 1

def daemon_run(config: Dict[str, Any], verbose: bool) -> int:
    """
    以守护进程模式运行扫描器

    参数:
        config: 配置字典
        verbose: 是否详细输出模式

    返回:
        退出代码
    """
    # 创建PID文件目录
    if not os.path.exists("pid"):
        os.makedirs("pid")

    # 生成PID文件路径
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pid_file = f"pid/scanner_{timestamp}.pid"

    # 记录守护进程信息
    print(f"将在后台运行扫描任务...")
    print(f"PID文件: {pid_file}")
    print(f"日志文件: log.txt")
    print(f"结果文件: results.txt")
    print("您可以关闭此终端，扫描将继续在后台执行")

    # 设置守护进程上下文
    context = daemon.DaemonContext(
        working_directory=os.getcwd(),
        umask=0o002,
        pidfile=lockfile.FileLock(pid_file),
        detach_process=True
    )

    # 启动守护进程
    with context:
        # 重新配置日志
        setup_logging(verbose=True)  # 守护进程模式总是使用详细日志
        logging.info(f"守护进程已启动，PID文件: {pid_file}")

        # 运行扫描器
        return run_scanner(config, verbose=True)

def check_files() -> None:
    """检查必要的文件是否存在"""
    files_ok = True

    # 检查配置文件
    if not os.path.exists("config.txt"):
        print("错误: 未找到配置文件 config.txt")
        print("请确保config.txt文件存在并正确配置")
        print("您可以从example目录复制一个配置文件示例")
        files_ok = False

    # 检查域名源文件
    if not os.path.exists("domains.txt") and not os.path.exists("generator_func.py"):
        print("错误: 未找到域名源文件 (domains.txt 或 generator_func.py)")
        print("您需要提供以下文件之一:")
        print("  - domains.txt: 每行一个域名基础部分")
        print("  - generator_func.py: 包含generate_domains()函数的Python脚本")
        print("示例文件可以在example目录中找到")
        files_ok = False

    # 如果文件检查失败，退出程序
    if not files_ok:
        print("\n您可以查看example目录中的示例文件作为参考")
        sys.exit(1)

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

        # 设置日志
        setup_logging(verbose=args.verbose)

        # 检查和创建必要的文件
        check_files()

        # 解析配置文件
        config_parser = ConfigParser()
        config = config_parser.parse_config()

        # 打印配置摘要
        logging.info("读取配置完成:")
        logging.info(f"TLD列表: {', '.join(config['tlds'])}")
        logging.info(f"查询间隔: {config['delay']}秒")
        logging.info(f"最大重试: {config['max_retries']}次")
        logging.info(f"通知方法: {config['notification_method']}")

        # 以守护进程模式运行扫描器
        return daemon_run(config, args.verbose)

    except Exception as e:
        print(f"发生未预期的错误: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
