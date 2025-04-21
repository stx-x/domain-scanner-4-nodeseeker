#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generators.py

域名生成器模块，提供从文件加载域名和执行用户自定义生成函数的功能。
支持灵活的域名生成策略，是域名扫描器的核心组件之一。
"""

import re
import sys
import os
import importlib.util
from typing import Generator, Set, Optional, Callable, List, Iterator, Dict, Any, cast
import logging

# 配置日志
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("generators")

# 域名验证相关常量
MAX_DOMAIN_LENGTH = 63  # 域名最大长度(不含TLD)
DOMAIN_REGEX = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$')


class DomainGenerator:
    """域名生成器类，用于生成或加载待检查的域名"""

    def __init__(self):
        """初始化域名生成器"""
        self.seen_domains: Set[str] = set()  # 用于去重

    def from_file(self, filepath: str) -> Generator[str, None, None]:
        """
        从文件加载域名

        参数:
            filepath: 域名文件路径，每行一个域名(不含TLD)

        生成:
            有效的域名主体部分(不含TLD)
        """
        if not os.path.exists(filepath):
            logger.error(f"文件不存在: {filepath}")
            raise FileNotFoundError(f"找不到域名文件: {filepath}")

        logger.info(f"从文件加载域名: {filepath}")
        line_count = 0
        valid_count = 0

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line_count += 1
                    domain_base = line.strip().lower()

                    # 跳过空行和注释行
                    if not domain_base or domain_base.startswith('#'):
                        continue

                    # 验证域名并去重
                    if self._is_valid_domain_base(domain_base):
                        if domain_base not in self.seen_domains:
                            self.seen_domains.add(domain_base)
                            valid_count += 1
                            yield domain_base

            logger.info(f"文件解析完成。总行数: {line_count}, 有效域名: {valid_count}")

        except UnicodeDecodeError as e:
            logger.error(f"文件编码错误: {e}")
            raise ValueError(f"无法解析文件 {filepath}: {e}")
        except Exception as e:
            logger.error(f"读取文件时出错: {e}")
            raise

    def from_function(self,
                     generator_func: Optional[Callable[[], Iterator[str]]] = None,
                     generator_file: Optional[str] = None) -> Generator[str, None, None]:
        """
        从自定义函数加载域名

        参数:
            generator_func: 直接传递的生成器函数
            generator_file: 包含生成器函数的Python文件路径

        生成:
            有效的域名主体部分(不含TLD)
        """
        # 从文件加载函数
        if generator_func is None and generator_file is not None:
            generator_func = self._load_generator_from_file(generator_file)

        if generator_func is None:
            logger.error("未提供有效的生成器函数")
            raise ValueError("必须提供生成器函数或包含生成器函数的文件")

        try:
            # 调用生成器函数
            logger.info("使用自定义函数生成域名...")
            processed_count = 0
            valid_count = 0

            for domain_base in generator_func():
                processed_count += 1

                # 转换为字符串并规范化
                if not isinstance(domain_base, str):
                    domain_base = str(domain_base)
                domain_base = domain_base.strip().lower()

                # 验证域名并去重
                if self._is_valid_domain_base(domain_base):
                    if domain_base not in self.seen_domains:
                        self.seen_domains.add(domain_base)
                        valid_count += 1
                        yield domain_base

                # 每处理一定数量的域名打印进度
                if processed_count % 10000 == 0:
                    logger.info(f"已处理 {processed_count} 个域名，找到 {valid_count} 个有效域名")

            logger.info(f"自定义函数执行完成。总处理: {processed_count}, 有效域名: {valid_count}")

        except Exception as e:
            logger.error(f"执行生成器函数时出错: {e}")
            raise ValueError(f"生成器函数执行失败: {e}")

    def _load_generator_from_file(self, filepath: str) -> Optional[Callable[[], Iterator[str]]]:
        """
        从文件加载生成器函数

        参数:
            filepath: Python文件路径

        返回:
            生成器函数对象或None(如果加载失败)
        """
        if not os.path.exists(filepath):
            logger.error(f"生成器文件不存在: {filepath}")
            raise FileNotFoundError(f"找不到生成器文件: {filepath}")

        try:
            logger.info(f"从文件加载生成器函数: {filepath}")

            # 使用importlib动态加载模块
            module_name = os.path.basename(filepath).replace('.py', '')
            spec = importlib.util.spec_from_file_location(module_name, filepath)

            if spec is None or spec.loader is None:
                logger.error(f"无法加载模块: {filepath}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # 获取生成器函数
            if hasattr(module, 'generate_domains'):
                generator_func = getattr(module, 'generate_domains')

                # 检查是否是可调用对象
                if callable(generator_func):
                    return cast(Callable[[], Iterator[str]], generator_func)
                else:
                    logger.error("'generate_domains' 不是一个可调用的函数")
            else:
                logger.error(f"在文件 {filepath} 中未找到 'generate_domains' 函数")

            return None

        except SyntaxError as e:
            logger.error(f"生成器文件语法错误: {e}")
            raise ValueError(f"生成器文件 {filepath} 包含语法错误: {e}")
        except Exception as e:
            logger.error(f"加载生成器文件时出错: {e}")
            raise ValueError(f"无法加载生成器文件 {filepath}: {e}")

    def _is_valid_domain_base(self, domain_base: str) -> bool:
        """
        验证域名基础部分是否有效

        参数:
            domain_base: 域名基础部分(不含TLD)

        返回:
            是否是有效的域名基础部分
        """
        # 检查是否为空
        if not domain_base:
            return False

        # 检查长度限制
        if len(domain_base) > MAX_DOMAIN_LENGTH:
            return False

        # 使用正则表达式检查格式
        # 域名必须由字母、数字和连字符组成
        # 不能以连字符开头或结尾
        # 不能有连续的连字符
        return bool(DOMAIN_REGEX.match(domain_base))

    def reset(self) -> None:
        """重置生成器状态，清除去重缓存"""
        self.seen_domains.clear()


# 辅助函数: 示例生成器函数
def sample_generator() -> Generator[str, None, None]:
    """示例生成器函数，生成一些样例域名"""
    # 简单示例: 生成a-z开头的三字符域名
    chars = 'abcdefghijklmnopqrstuvwxyz'
    for c1 in chars:
        for c2 in chars[:3]:  # 仅使用前几个字符作为示例
            for c3 in chars[:3]:
                yield f"{c1}{c2}{c3}"


# 测试代码
if __name__ == "__main__":
    # 简单的测试函数
    def test_generators():
        generator = DomainGenerator()

        print("\n=== 测试示例生成器函数 ===")
        count = 0
        for domain in generator.from_function(generator_func=sample_generator):
            print(domain)
            count += 1
            if count >= 10:
                print("...更多结果省略...")
                break

        # 创建临时测试文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as tmp:
            tmp.write("example\n")
            tmp.write("test-domain\n")
            tmp.write("invalid--domain\n")  # 无效域名
            tmp.write("012345\n")
            tmp_path = tmp.name

        print(f"\n=== 测试从文件加载域名: {tmp_path} ===")
        try:
            for domain in generator.from_file(tmp_path):
                print(domain)
        finally:
            # 清理临时文件
            os.unlink(tmp_path)

        # 创建临时测试生成器文件
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.py') as tmp:
            tmp.write("""
def generate_domains():
    \"\"\"测试生成器\"\"\"
    yield "test1"
    yield "test2"
    yield "test-3"
    yield "invalid--4"  # 无效域名
""")
            generator_path = tmp.name

        print(f"\n=== 测试从文件加载生成器函数: {generator_path} ===")
        try:
            for domain in generator.from_function(generator_file=generator_path):
                print(domain)
        finally:
            # 清理临时文件
            os.unlink(generator_path)

    test_generators()
