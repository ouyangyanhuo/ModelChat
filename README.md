# 模型对话插件
## 简介
基于 Ncatbot 的大模型对话插件，支持本地大模型加载、远程大模型调用，拥有图像识别功能，同时为大模型添加了短期记忆功能，针对每个 QQ 号拥有记忆能力。

- 本地模型使用 [ollama](https://ollama.com/)
- 远程模型支持所有 OpenAI 接口兼容的模型，包含 ChatGPT、Moonshot、Qwen、Deepseek 等
- 图像识别大模型需要调用支持图像识别的模型，可以分开调用 图像识别 和 文本对话 的API

## 开始使用
指令：
- `/chat [对话内容]`     对话
- `/clear chat_history` 清除对话记录

## 使用配置
-  安装依赖

```
pip install -r requirements.txt
```

- 配置文件

将 `config.yml.template` 重命名为 `config.yml`，并且修改配置文件

## 注意事项

- 模型的记忆文件位于插件目录 `/cache/history.json`，没有该文件会自动生成

- 用户若要使用本地大模型，请先安装 Ollama 运行环境

- 介于本地大模型能力，暂不支持本地大模型的图像识别

- 解压文件夹名称必须为 ModelChat

目录结构如下：
```
ModelChat/
├── cache/
│   └── history.json
├── __init__.py
├── chat.py
├── config.yml
└── main.py
```

## 作者
[Magneto](https://fmcf.cc)

## 更新日志
- 1.2.0
  - 违禁词检测
  - Markdown 格式符号清理
- 1.1.0
  - 图像识别
  - 清除记忆指令
  - requirements.txt
- 1.0.0
  - 本地大模型
  - 云端大模型
  - 多模型切换
  - 大模型记忆
## 许可证
GNU GENERAL PUBLIC LICENSE 3.0