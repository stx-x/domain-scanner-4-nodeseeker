#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
triple_letter_domains.py

示例生成器：生成包含三个相同字母的四字符域名。
例如：aaab, baaa, aaac, caaa 等。
"""

def generate_domains():
    """
    生成所有包含三个相同字母的四字符域名

    这个函数生成两种模式的域名：
    1. 三个相同字母开头，后跟一个不同字母 (例如：aaab)
    2. 一个字母开头，后跟三个相同的字母 (例如：baaa)

    返回:
        一个生成器，产生所有符合条件的域名
    """
    letters = 'abcdefghijklmnopqrstuvwxyz'

    # 生成模式：aaa + x
    for repeated in letters:
        for last in letters:
            if repeated != last:  # 确保最后一个字母不同
                domain = f"{repeated}{repeated}{repeated}{last}"
                yield domain

    # 生成模式：x + aaa
    for first in letters:
        for repeated in letters:
            if first != repeated:  # 确保第一个字母不同
                domain = f"{first}{repeated}{repeated}{repeated}"
                yield domain

# 如果直接运行此文件，则执行简单测试
if __name__ == "__main__":
    # 计算并打印将生成的域名总数
    letters_count = len('abcdefghijklmnopqrstuvwxyz')
    total = letters_count * (letters_count - 1) * 2  # 两种模式

    print(f"这个生成器将创建 {total} 个域名")
    print("示例域名:")

    # 打印一些示例
    generator = generate_domains()
    for i, domain in enumerate(generator):
        print(domain)
        if i >= 14:  # 只显示前15个
            print("...")
            break
