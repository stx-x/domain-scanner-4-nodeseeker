#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基于词典的域名生成器示例

展示了如何使用词典文件生成域名组合
"""

import os
import random

def generate_domains():
    """基于词典的域名生成器函数"""

    # 内置简短词典
    common_words = [
        "time", "year", "day", "week", "month", "way", "thing", "man", "world",
        "life", "hand", "part", "child", "eye", "woman", "place", "work", "case",
        "point", "group", "company", "number", "right", "fact", "home", "water",
        "money", "night", "area", "book", "word", "side", "kind", "head", "house",
        "page", "face", "news", "school", "story", "power", "line", "end", "member",
        "law", "car", "city", "name", "team", "game", "food", "sun", "air", "net",
        "shop", "art", "war", "land", "call", "level", "hour", "type", "film", "data",
        "form", "event", "plan", "room", "room", "lot", "mind", "need", "job", "road"
    ]

    # 示例1: 单词组合
    for i, word1 in enumerate(common_words):
        # 单个单词
        yield word1

        # 限制组合数量，避免生成过多
        if i < 20:  # 仅为前20个单词生成组合
            # 两个单词组合
            for j, word2 in enumerate(common_words):
                if i != j:  # 避免重复单词
                    yield f"{word1}{word2}"

                    # 带连字符的组合
                    if j < 5:  # 进一步限制，仅生成少量组合
                        yield f"{word1}-{word2}"

    # 示例2: 单词+数字组合
    for word in common_words[:10]:  # 仅使用前10个单词
        for num in range(10):  # 数字0-9
            yield f"{word}{num}"
            yield f"{num}{word}"

    # 示例3: 从外部文件加载词典(如果存在)
    # 这部分通常需要调整为您自己的词典文件路径
    wordlist_path = os.path.join("wordlists", "english.txt")
    if os.path.exists(wordlist_path):
        try:
            with open(wordlist_path, 'r', encoding='utf-8') as f:
                external_words = [line.strip() for line in f]

                # 随机选择一部分单词，避免使用整个词典
                sample_size = min(100, len(external_words))
                sampled_words = random.sample(external_words, sample_size)

                # 生成单词
                for word in sampled_words:
                    if 3 <= len(word) <= 10:  # 仅使用适当长度的单词
                        yield word
        except Exception as e:
            print(f"读取外部词典出错: {e}")
            # 出错时忽略，继续使用内置词典
