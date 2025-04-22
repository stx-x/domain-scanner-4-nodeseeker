# Domain Availability Scanner

一个高效、灵活的域名可注册性检测工具，基于RDAP协议检查多种顶级域名(TLD)的可用性。

## 功能特点

- 使用现代RDAP协议进行域名查询，比传统WHOIS更快速可靠
- 支持多种顶级域名(TLD)检测
- 多种域名获取方式：文件导入或自定义生成函数
- 智能重试和错误处理机制
- 结果实时输出并保存到文件

## 安装方法

### 要求
- Python 3.7+
- 必要的Python库: requests

### 安装步骤

1. 克隆项目到本地
```
git clone https://github.com/stx-x/domain-scanner-4-nodeseeker
cd domain-scanner-4-nodeseeker
```

2. 安装依赖
你需要配置虚拟环境，如果你不知道是什么，看看这个[venv](https://docs.python.org/zh-cn/3.13/tutorial/venv.html)
```
pip3 install -r requirements.txt
```

## 使用方法

### 基本用法

从文件读取域名列表进行扫描:
```
pythoh3 main.py -t .com .org -f domains.txt -o results.txt
```

使用自定义生成器函数:
```
python3 main.py -t .li .de -g my_generator.py -o results.txt
```

### 参数说明

```
用法: main.py [选项]

选项:
  -t, --tlds TLD [TLD ...]     要检查的顶级域名列表 (例如: .com .org .net)
  -f, --file FILE              从文件读取域名列表
  -g, --generator-file FILE    使用自定义生成器函数文件
  -d, --delay DELAY            查询间隔(秒) [默认: 1.0]
  -r, --max-retries RETRIES    最大重试次数 [默认: 2]
  -o, --output FILE            输出结果文件 [必需参数]
  -v, --verbose                详细输出模式, 不能注册的扫描结果也会显示
```

### 域名文件格式

域名文件应包含每行一个域名基础部分(不含TLD)，例如:
```
example
domain
mysite
baidu
google
github
```

工具会自动将这些基础名称与指定的TLD组合，如 `example.com`, `example.org` 等。

## 自定义域名生成函数

您可以提供自己的域名生成函数，以便灵活地创建想要检查的域名列表。

### 创建生成器函数文件

1. 创建一个Python文件(例如 `my_generator.py`)
2. 在文件中定义一个名为 `generate_domains` 的函数
3. 该函数应使用 `yield` 语句产生域名（不含TLD部分）

示例 `my_generator.py`:

```python
def generate_domains():
    """生成包含三个'o'的四字符域名"""
    chars = 'abcdefghijklmnpqrstuvwxyz'  # 不含'o'

    # 生成'ooo'前缀加一个字符
    for c in chars:
        yield f"ooo{c}"

    # 生成其他位置组合
    for c in chars:
        yield f"oo{c}o"
        yield f"o{c}oo"
        yield f"{c}ooo"
```

## 使用AI生成自定义函数

使用大语言模型(如ChatGPT、Claude等)可以帮助您生成复杂的域名生成函数。以下是一些高效的提示模板:

### 基础提示模板

```
请编写一个名为generate_domains的Python函数，使用生成器(yield)返回符合以下条件的域名基础部分(不含TLD):

[在这里描述您需要的域名模式]

要求:
1. 函数不接受任何参数
2. 使用yield语句返回每个域名
3. 域名只包含字母、数字或连字符(-)
4. 域名不能以连字符开头或结尾
5. 返回的域名不包含TLD部分(如.com或.org)
6. 函数应高效，避免产生重复域名

请只返回函数代码，不需要解释。
```

### 示例提示(按具体需求)

#### 1. 特定长度和字符模式

```
请编写一个名为generate_domains的Python函数，使用生成器(yield)返回符合以下条件的域名基础部分:

- 长度为5个字符
- 包含至少2个数字
- 数字不能相邻出现
- 字母部分只使用辅音字母(不包含a,e,i,o,u)

要求:
1. 函数不接受任何参数
2. 使用yield语句返回每个域名
3. 函数应高效，避免产生重复域名

请只返回函数代码，不需要解释。
```

#### 2. 基于特定词汇或行业

```
请编写一个名为generate_domains的Python函数，使用生成器(yield)返回以下特点的域名基础部分:

- 与人工智能/机器学习相关
- 包含以下词根之一: "ai", "ml", "deep", "neural", "bot"
- 长度在3-10个字符之间
- 可以是合成词、缩写或创意组合

要求:
1. 函数不接受任何参数
2. 使用yield语句返回每个域名
3. 域名应简洁、易记、有意义
4. 生成约100-200个不同的域名候选

请只返回函数代码，不需要解释。
```

#### 3. 特殊字符模式

```
请编写一个名为generate_domains的Python函数，使用生成器(yield)返回以下特点的域名基础部分:

- 长度为4个字符
- 包含恰好3个字母"x"
- 剩余位置可以是任何小写字母(a-z)
- 生成所有可能的组合

要求:
1. 函数不接受任何参数
2. 使用yield语句返回每个域名
3. 避免重复组合

请只返回函数代码，不需要解释。
```

#### 4. 中文拼音相关域名

```
请编写一个名为generate_domains的Python函数，使用生成器(yield)返回以下特点的域名基础部分:

- 基于常用中文词语的拼音
- 与[教育/科技/金融/健康]行业相关
- 长度不超过12个字符
- 可以是完整拼音或缩写形式

要求:
1. 函数不接受任何参数
2. 使用yield语句返回每个域名
3. 域名只包含字母(不含声调)
4. 生成约50-100个有意义的域名

请只返回函数代码，不需要解释。
```

### AI生成后的检查要点

从AI获取代码后，请检查以下几点:

1. 函数名是否为 `generate_domains`
2. 函数是否正确使用了 `yield` 而不是 `return`
3. 生成的域名是否符合域名规则 (只包含字母、数字、连字符)
4. 域名是否不以连字符开头或结尾
5. 函数是否没有无限循环或其他潜在问题

### 函数要求总结:

1. 函数名必须是 `generate_domains`
2. 不需要参数
3. 使用 `yield` 语句返回每个域名（不含TLD）
4. 确保每个生成的域名只包含允许的字符（字母、数字和连字符）
5. 避免生成无效域名（如以连字符开头或结尾）

## 示例

### 检查短域名可用性
```
# 检查所有3字符.com和.net域名
python3 main.py -t .com .net -g generators/three_chars.py -o short_domains.txt
```

### 检查包含特定关键词的域名
```
# 检查包含"crypto"的域名
python3 main.py -t .com .io -f keywords/crypto_domains.txt -o crypto_domains.txt
```

## 注意事项

- 请遵守RDAP服务器的使用政策，避免过于频繁的查询
- 某些TLD的RDAP服务器可能有不同的速率限制，请适当调整--delay参数
- 域名可用性检查结果仅供参考，最终注册状态以注册商为准

## 状态码说明

工具使用HTTP状态码判断域名可用性:

- 404: 域名未注册，通常可注册
- 200/401: 域名已注册或不可注册
- 400: 无效请求，包含非法字符或格式错误
- 429: 查询过于频繁，触发速率限制

## 待开发功能

1. 添加更多RDAP服务器支持，提高特定TLD的查询精确度
2. 实现在线查询模式，支持通过Web界面进行域名查询
3. 开发跨平台桌面应用程序版本，支持Windows/macOS/Linux


## 许可证

MIT License
