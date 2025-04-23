#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
uploader.py

结果文件上传模块，负责将扫描结果上传到HedgeDoc或其他服务，
并返回可分享的URL。
"""

import requests
import os
import logging
from urllib.parse import urlparse
from typing import Optional, Tuple, Dict, Any

# 配置日志
logger = logging.getLogger("uploader")

class ResultUploader:
    """结果文件上传器，支持将Markdown文件上传到HedgeDoc服务"""

    def __init__(self, hedgedoc_url: str = "https://domain.gfw.li"):
        """
        初始化上传器

        参数:
            hedgedoc_url: HedgeDoc服务的基础URL
        """
        self.hedgedoc_url = hedgedoc_url.rstrip('/')
        logger.info(f"初始化结果上传器，目标服务: {self.hedgedoc_url}")

    def upload_markdown_content(self, markdown_content: str, title: str = "域名扫描结果") -> Tuple[bool, str, Optional[str]]:
        """
        上传Markdown内容到HedgeDoc

        参数:
            markdown_content: Markdown内容
            title: 文档标题

        返回:
            (成功状态, 消息, 分享URL)元组
        """
        logger.info(f"准备上传Markdown内容，标题: {title}")

        try:
            # 添加标题
            if not markdown_content.startswith("# "):
                markdown_content = f"# {title}\n\n{markdown_content}"

            # 步骤1: 创建笔记
            create_url = f"{self.hedgedoc_url}/new"
            headers = {'Content-Type': 'text/markdown; charset=utf-8'}

            logger.debug(f"发送POST请求到: {create_url}")
            # 发送POST请求创建笔记
            response = requests.post(
                create_url,
                data=markdown_content.encode('utf-8'),
                headers=headers,
                allow_redirects=False  # 不自动跟随重定向
            )

            # 检查是否重定向(通常是302)并获取Location头部
            if response.status_code in (301, 302, 303, 307, 308) and 'Location' in response.headers:
                editable_url = response.headers['Location']
                logger.debug(f"获取到编辑URL: {editable_url}")

                # 从URL中提取Note ID
                parsed_url = urlparse(editable_url)
                note_id = os.path.basename(parsed_url.path)  # 获取路径的最后一部分

                if not note_id:
                    raise ValueError("无法从编辑URL中提取Note ID")

                logger.debug(f"提取到Note ID: {note_id}")

                # 步骤2: 获取发布URL
                publish_endpoint_url = f"{self.hedgedoc_url}/{note_id}/publish"
                logger.debug(f"请求发布URL: {publish_endpoint_url}")

                # 发送GET请求获取发布URL
                response = requests.get(
                    publish_endpoint_url,
                    allow_redirects=False  # 不自动跟随重定向
                )

                if response.status_code in (301, 302, 303, 307, 308) and 'Location' in response.headers:
                    publish_url = response.headers['Location']
                    logger.info(f"成功获取发布URL: {publish_url}")

                    # 返回成功状态和发布URL
                    return True, "内容上传成功", publish_url
                else:
                    error_msg = f"未能获取发布URL，状态码: {response.status_code}"
                    logger.error(error_msg)
                    return False, error_msg, None
            else:
                error_msg = f"创建笔记失败，状态码: {response.status_code}"
                logger.error(error_msg)
                return False, error_msg, None

        except requests.exceptions.RequestException as e:
            error_msg = f"请求异常: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
        except ValueError as e:
            error_msg = f"处理URL时出错: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"上传过程中发生未知错误: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None

    def upload_markdown_file(self, file_path: str) -> Tuple[bool, str, Optional[str]]:
        """
        上传Markdown文件到HedgeDoc

        参数:
            file_path: Markdown文件路径

        返回:
            (成功状态, 消息, 分享URL)元组
        """
        logger.info(f"准备上传文件: {file_path}")

        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"文件未找到: {file_path}"
            logger.error(error_msg)
            return False, error_msg, None

        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()

            # 调用上传内容的方法
            return self.upload_markdown_content(markdown_content)

        except UnicodeDecodeError:
            error_msg = f"文件编码错误，请确保文件为UTF-8编码"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"读取文件时发生错误: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, None
