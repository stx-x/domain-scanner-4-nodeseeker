#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
config_parser.py

配置文件解析模块，负责读取和解析config.txt文件，
提供默认配置和配置验证功能。
"""

import os
import logging
from typing import Dict, Any, List, Optional

# 默认配置
DEFAULT_CONFIG = {
    "tlds": [".com", ".org", ".net"],
    "delay": 1.0,
    "max_retries": 2,
    "hedgedoc_url": "https://domain.gfw.li",
    "domain_source": "auto",  # auto, file, generator
    "notification_method": "none",  # none, email, telegram等
    "notification_config": {},      # 通知配置,如email地址等
}

class ConfigParser:
    """配置解析器类，处理配置文件的读取和验证"""

    def __init__(self, config_path: str = "config.txt"):
        """
        初始化配置解析器

        参数:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.logger = logging.getLogger("config")
        self.config = DEFAULT_CONFIG.copy()

    def parse_config(self) -> Dict[str, Any]:
        """
        解析配置文件

        返回:
            配置字典
        """
        if not os.path.exists(self.config_path):
            self.logger.warning(f"配置文件 {self.config_path} 不存在，将创建默认配置")
            self._create_default_config()
            return self.config

        try:
            self.logger.info(f"正在读取配置文件: {self.config_path}")
            with open(self.config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue

                    # 解析键值对
                    try:
                        key, value = [part.strip() for part in line.split('=', 1)]
                        self._process_config_item(key, value)
                    except ValueError:
                        self.logger.warning(f"无法解析配置行: {line}")

            # 验证配置
            self._validate_config()
            return self.config

        except Exception as e:
            self.logger.error(f"读取配置文件时出错: {e}", exc_info=True)
            self.logger.warning("使用默认配置继续")
            return DEFAULT_CONFIG.copy()

    def _process_config_item(self, key: str, value: str) -> None:
        """
        处理单个配置项

        参数:
            key: 配置键
            value: 配置值字符串
        """
        if key == "tlds":
            # 处理TLD列表
            tlds = [tld.strip() for tld in value.split(',')]
            # 确保所有TLD都以.开头
            tlds = [tld if tld.startswith('.') else f'.{tld}' for tld in tlds]
            self.config["tlds"] = tlds

        elif key == "domain_source":
            if value in ["auto", "file", "generator"]:
                self.config["domain_source"] = value
            else:
                self.logger.warning(f"无效的domain_source值: {value}，使用默认值: {DEFAULT_CONFIG['domain_source']}")

        elif key == "delay":
            try:
                delay = float(value)
                self.config["delay"] = max(0.1, delay)  # 至少0.1秒
            except ValueError:
                self.logger.warning(f"无效的delay值: {value}，使用默认值: {DEFAULT_CONFIG['delay']}")

        elif key == "max_retries":
            try:
                retries = int(value)
                self.config["max_retries"] = max(0, retries)
            except ValueError:
                self.logger.warning(f"无效的max_retries值: {value}，使用默认值: {DEFAULT_CONFIG['max_retries']}")

        elif key == "hedgedoc_url":
            self.config["hedgedoc_url"] = value.rstrip('/')

        elif key == "notification_method":
            self.config["notification_method"] = value

        elif key.startswith("notification_"):
            # 存储通知相关的其他配置
            subkey = key[13:]  # 去掉"notification_"前缀
            if "notification_config" not in self.config:
                self.config["notification_config"] = {}
            self.config["notification_config"][subkey] = value

        else:
            self.logger.warning(f"未知配置项: {key}")

    def _validate_config(self) -> None:
        """验证配置是否有效"""
        # 确保必要的配置项存在
        if not self.config.get("tlds"):
            self.logger.warning("配置中未设置TLD，使用默认TLD")
            self.config["tlds"] = DEFAULT_CONFIG["tlds"]

        # 验证通知设置
        method = self.config.get("notification_method", "none")
        if method not in ["none", "email", "telegram"]:
            self.logger.warning(f"不支持的通知方法: {method}，使用'none'")
            self.config["notification_method"] = "none"

        # 如果使用email通知，确保有邮箱地址
        if method == "email" and not self.config.get("notification_config", {}).get("email"):
            self.logger.warning("选择了Email通知但未提供邮箱地址，通知功能将被禁用")
            self.config["notification_method"] = "none"

    def _create_default_config(self) -> None:
        """创建默认配置文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write("""# 域名扫描器配置文件
# 修改配置后生效，不需要修改代码

# 要扫描的顶级域名列表，多个TLD用逗号分隔
tlds = .com, .org, .net

# 查询间隔(秒)，建议不小于0.5秒，避免触发速率限制
delay = 1.0

# 查询失败时的最大重试次数
max_retries = 2

# HedgeDoc服务URL，用于上传结果
hedgedoc_url = https://domain.gfw.li

# 通知方法: none, email, telegram
notification_method = none

# 邮件通知配置 (当notification_method = email时生效)
notification_email = your-email@example.com

# Telegram通知配置 (当notification_method = telegram时生效)
notification_telegram_token = your-bot-token
notification_telegram_chat_id = your-chat-id
""")
                self.logger.info(f"已创建默认配置文件: {self.config_path}")
        except Exception as e:
            self.logger.error(f"创建默认配置文件失败: {e}")
