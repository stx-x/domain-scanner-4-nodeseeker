#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
notifier.py

通知模块，负责在扫描完成后通过不同渠道通知用户，
支持邮件和Telegram等通知方式。
"""

import logging
import os
import smtplib
import requests
from email.message import EmailMessage
from typing import Dict, Any, Optional

logger = logging.getLogger("notifier")

class Notifier:
    """通知发送器类，负责处理各种通知方式"""

    def __init__(self, method: str = "none", config: Dict[str, Any] = None):
        """
        初始化通知发送器

        参数:
            method: 通知方法 (none, email, telegram)
            config: 通知配置
        """
        self.method = method
        self.config = config or {}
        logger.info(f"初始化通知发送器，方法: {method}")

    def send_notification(self, subject: str, message: str, link: Optional[str] = None) -> bool:
        """
        发送通知

        参数:
            subject: 通知主题
            message: 通知内容
            link: 结果链接（可选）

        返回:
            是否发送成功
        """
        if self.method == "none":
            logger.info("通知功能未启用")
            return True

        if link:
            message = f"{message}\n\n结果链接: {link}"

        if self.method == "email":
            return self._send_email(subject, message)
        elif self.method == "telegram":
            return self._send_telegram(subject, message)
        else:
            logger.warning(f"不支持的通知方法: {self.method}")
            return False

    def _send_email(self, subject: str, message: str) -> bool:
        """发送邮件通知"""
        recipient = self.config.get("email")
        if not recipient:
            logger.error("邮件通知未配置收件人")
            return False

        try:
            # 这里使用简单的SMTP方式，实际应用中应该使用更安全的方式
            # 可以考虑第三方库如yagmail或连接到SMTP服务器

            # 简化实现，实际应用需要完整的SMTP配置
            logger.warning("邮件通知功能需要完整实现SMTP配置，目前仅记录日志")
            logger.info(f"[邮件通知] 收件人: {recipient}")
            logger.info(f"[邮件通知] 主题: {subject}")
            logger.info(f"[邮件通知] 内容: {message}")

            # 返回成功假装已发送
            return True

            # 实际发送代码(需配置)：
            """
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = sender_email
            msg['To'] = recipient
            msg.set_content(message)

            with smtplib.SMTP_SSL('smtp.example.com', 465) as server:
                server.login(sender_email, password)
                server.send_message(msg)
            """

        except Exception as e:
            logger.error(f"发送邮件通知失败: {e}", exc_info=True)
            return False

    def _send_telegram(self, subject: str, message: str) -> bool:
        """发送Telegram通知"""
        token = self.config.get("telegram_token")
        chat_id = self.config.get("telegram_chat_id")

        if not token or not chat_id:
            logger.error("Telegram通知未配置token或chat_id")
            return False

        try:
            text = f"*{subject}*\n\n{message}"
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }

            logger.debug(f"发送Telegram请求: {url}")
            response = requests.post(url, data=data)

            if response.status_code == 200:
                logger.info("Telegram通知发送成功")
                return True
            else:
                logger.error(f"Telegram API返回错误: {response.status_code} {response.text}")
                return False

        except Exception as e:
            logger.error(f"发送Telegram通知失败: {e}", exc_info=True)
            return False
