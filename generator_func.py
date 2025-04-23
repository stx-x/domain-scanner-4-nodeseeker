#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generator_func.py

DomainSeeker 默认域名生成器函数。
此文件必须包含一个名为generate_domains的函数，用于生成域名基础部分。
"""

def generate_domains():
    """
    生成要检查的域名基础部分。

    注意：
    1. 函数名必须是generate_domains
    2. 函数应返回一个迭代器，每次产生一个域名基础部分（不含TLD）
    3. TLD (.com, .org等)将根据config.txt中的配置自动添加

    参考示例目录中的示例了解更多生成方式。
    """
    # 简单域名列表示例
    domains = [
        "example",
        "test",
        "mywebsite",
        "cool-domain"
    ]

    # 返回域名
    for domain in domains:
        yield domain

    # 简单组合示例 (前缀+单词)
    prefixes = ["my", "best", "top"]
    words = ["app", "site", "blog"]

    for prefix in prefixes:
        for word in words:
            yield f"{prefix}{word}"
