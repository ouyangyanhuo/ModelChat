# 模型对话插件
## 简介
基于 Ncatbot 的大模型对话插件，支持本地大模型加载、远程大模型调用，同时为大模型添加了短期记忆功能，针对每个 QQ 号拥有记忆能力。

- 本地模型使用 [ollama](https://ollama.com/)
- 远程模型支持所有 OpenAI 接口兼容的模型，包含 ChatGPT、Moonshot、Qwen、Deepseek 等

## 开始使用
指令：`/chat [对话内容]`

## 使用配置
-  依赖（暂未编写requirements.txt）
```
openai
ollama
```
- 配置文件
将 `config.yml.template` 重命名为 `config.yml`，并且修改配置文件
```
api_key：你的 OpenAI API Key
base_url：你的 OpenAI API 地址
use_local_model：是否启用本地大模型，如果启用本地大模型，将不会使用 api_key 和 basese_url
model: 你的模型名称
memory_length：聊天记录记忆长度，每个账号拥有的所有对话长度，包含用户提问、AI回复，例如：用户提问后AI回答，则记为两条。
system_prompt：大模型提示词，用于为大模型设置一个初始设定，例如名字、性别、年龄等
```
## 作者
[Magneto](https://fmcf.cc)

## 许可证
GNU GENERAL PUBLIC LICENSE 3.0