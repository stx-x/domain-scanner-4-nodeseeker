#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
main.py

域名可用性扫描工具的主程序入口点。
这个脚本是用户执行的主要入口，它调用命令行接口进行参数处理
并启动扫描流程。
"""

import sys
import os

# 添加当前目录到Python路径，确保能够导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入命令行接口模块
from core.cli import main

if __name__ == "__main__":
    # 调用命令行接口的主函数并传递退出代码
    sys.exit(main())
