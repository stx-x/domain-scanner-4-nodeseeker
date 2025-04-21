#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
three_char_domains.py

示例生成器：生成所有可能的三字符域名。
这个文件展示了如何创建一个自定义域名生成器函数。
"""

def generate_domains():
    """
    生成所有可能的三字符域名

    这个函数生成由小写字母(a-z)组成的所有3字符组合。
    总共会生成 26³ = 17,576 个域名。

    返回:
        一个生成器，产生所有三字符域名
    """
    chars = 'abcdefghijklmnopqrstuvwxyz'

    # 使用三层嵌套循环生成所有可能的组合
    for c1 in chars:
        for c2 in chars:
            for c3 in chars:
                domain = f"{c1}{c2}{c3}"
                yield domain

# 如果直接运行此文件，则执行简单测试
if __name__ == "__main__":
    # 打印前10个生成的域名作为示例
    print("生成的前10个三字符域名示例:")

    generator = generate_domains()
    for i, domain in enumerate(generator):
        print(domain)
        if i >= 9:  # 只显示前10个
            print("...")
            print(f"共有26³ = 17,576个可能的组合")
            break
