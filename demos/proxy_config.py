#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Jupyter Notebook 代理配置工具
提供多种方式在 Jupyter 中设置 Python 代理
"""

import os
from typing import Optional, Dict


def set_proxy(
    http_proxy: Optional[str] = None,
    https_proxy: Optional[str] = None,
    no_proxy: Optional[str] = None
) -> Dict[str, str]:
    """
    通过环境变量设置系统级代理
    
    参数:
        http_proxy: HTTP 代理地址，格式: http://host:port 或 http://user:pass@host:port
        https_proxy: HTTPS 代理地址，格式同上
        no_proxy: 不使用代理的地址列表，用逗号分隔，如: 'localhost,127.0.0.1'
    
    返回:
        设置后的代理环境变量字典
    """
    if http_proxy:
        os.environ['HTTP_PROXY'] = http_proxy
        os.environ['http_proxy'] = http_proxy  # 小写版本，某些库需要
    
    if https_proxy:
        os.environ['HTTPS_PROXY'] = https_proxy
        os.environ['https_proxy'] = https_proxy  # 小写版本，某些库需要
    
    if no_proxy:
        os.environ['NO_PROXY'] = no_proxy
        os.environ['no_proxy'] = no_proxy
    
    return {
        'HTTP_PROXY': os.environ.get('HTTP_PROXY', ''),
        'HTTPS_PROXY': os.environ.get('HTTPS_PROXY', ''),
        'NO_PROXY': os.environ.get('NO_PROXY', '')
    }


def unset_proxy():
    """清除所有代理设置"""
    proxy_vars = ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 
                  'NO_PROXY', 'no_proxy']
    for var in proxy_vars:
        os.environ.pop(var, None)


def get_proxy_config() -> Dict[str, str]:
    """获取当前的代理配置"""
    return {
        'HTTP_PROXY': os.environ.get('HTTP_PROXY', '未设置'),
        'HTTPS_PROXY': os.environ.get('HTTPS_PROXY', '未设置'),
        'NO_PROXY': os.environ.get('NO_PROXY', '未设置')
    }


def print_proxy_config():
    """打印当前的代理配置"""
    config = get_proxy_config()
    print("=" * 50)
    print("当前代理配置:")
    print("=" * 50)
    for key, value in config.items():
        print(f"{key}: {value}")
    print("=" * 50)


# 便捷函数：快速设置常用代理
def set_local_proxy(port: int = 7890):
    """设置本地代理（常见端口如 7890, 1080 等）"""
    proxy = f'http://127.0.0.1:{port}'
    return set_proxy(http_proxy=proxy, https_proxy=proxy)


def set_socks5_proxy(host: str = '127.0.0.1', port: int = 1080):
    """设置 SOCKS5 代理"""
    proxy = f'socks5://{host}:{port}'
    return set_proxy(http_proxy=proxy, https_proxy=proxy)


# 示例用法
if __name__ == '__main__':
    # 示例 1: 设置本地 HTTP 代理
    print("示例 1: 设置本地代理")
    set_local_proxy(7890)
    print_proxy_config()
    
    # 示例 2: 设置带认证的代理
    print("\n示例 2: 设置带认证的代理")
    set_proxy(
        http_proxy='http://username:password@proxy.example.com:8080',
        https_proxy='http://username:password@proxy.example.com:8080'
    )
    print_proxy_config()
    
    # 示例 3: 清除代理
    print("\n示例 3: 清除代理设置")
    unset_proxy()
    print_proxy_config()

