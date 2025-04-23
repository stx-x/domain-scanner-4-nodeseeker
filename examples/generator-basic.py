#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基础域名生成器示例

展示了几种简单的域名生成方法
"""

def generate_domains():
    """基础域名生成器函数"""

    # 示例1: 直接列表
    basic_domains = [
        "example",
        "test",
        "demo",
        "sample"
    ]

    for domain in basic_domains:
        yield domain

    # 示例2: 前缀+单词组合
    prefixes = ["my", "best", "top", "the", "get", "try"]
    words = ["app", "site", "web", "tech", "blog", "cloud", "host", "code"]

    for prefix in prefixes:
        for word in words:
            # 无连字符组合
            yield f"{prefix}{word}"

            # 带连字符组合
            yield f"{prefix}-{word}"

    # 示例3: 简单字母+数字组合
    # 注意: 此示例仅生成少量组合，实际使用时可能需要限制生成量
    chars = "abcde"  # 仅使用前5个字母作为示例

    for char in chars:
        for num in range(5):  # 仅使用0-4五个数字
            yield f"{char}{num}"
            yield f"{num}{char}"
