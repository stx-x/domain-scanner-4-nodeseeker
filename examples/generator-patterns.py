#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
模式域名生成器示例

展示了使用特定模式生成域名的方法
"""

import itertools
import random

def generate_domains():
    """模式域名生成器函数"""

    # 示例1: 生成所有2字母+2数字组合
    # 注意: 这会生成大量组合，实际使用时请考虑限制生成量
    letters = "abcdefghijklmnopqrstuvwxyz"
    digits = "0123456789"

    # 仅使用前5个字母和数字作为示例，避免生成过多
    # 实际使用时可以取消这个限制
    letters_sample = letters[:5]  # "abcde"
    digits_sample = digits[:5]    # "01234"

    # 生成字母+数字组合
    for l1 in letters_sample:
        for l2 in letters_sample:
            for d1 in digits_sample:
                for d2 in digits_sample:
                    yield f"{l1}{l2}{d1}{d2}"

    # 示例2: 短词+短词组合
    prefixes = ["web", "app", "net", "dev", "top", "get", "try", "buy", "use"]
    suffixes = ["pro", "hub", "lab", "app", "box", "now", "run", "kit", "go"]

    for prefix in prefixes:
        for suffix in suffixes:
            yield f"{prefix}{suffix}"

    # 示例3: 特殊替换模式 (leet speak)
    # 例如: a -> 4, e -> 3, i -> 1, o -> 0
    words = ["secure", "private", "crypto", "elite", "master", "hacker", "code"]
    leet_map = {'a': '4', 'e': '3', 'i': '1', 'o': '0', 's': '5', 't': '7'}

    for word in words:
        # 原始单词
        yield word

        # 基本leet转换(转换所有可能的字符)
        leet_word = ''
        for char in word:
            leet_word += leet_map.get(char, char)
        yield leet_word

        # 随机leet转换(随机转换部分字符)
        for i in range(3):  # 为每个单词生成3个随机变体
            rand_leet = ''
            for char in word:
                if char in leet_map and random.random() > 0.5:
                    rand_leet += leet_map[char]
                else:
                    rand_leet += char
            yield rand_leet
