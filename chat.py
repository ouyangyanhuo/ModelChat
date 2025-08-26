from openai import OpenAI
from ncatbot.core import GroupMessage
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage,SystemMessage, AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from .utils import ConfigManager,SystemPromptManager
import json, os, requests, base64,re

class BaseChatModel:
    """聊天模型的基类"""
    def __init__(self, plugin_dir):
        """初始化参数"""
        self.plugin_dir = plugin_dir
        self.config_manager = ConfigManager(plugin_dir)
        self.config = self.config_manager.load_config()
        self.data_config = self.config_manager.load_data()
        # 初始化历史记录存储
        self.history_file = os.path.abspath(os.path.join(plugin_dir, './cache/history.json')).replace("\\", "/")
        self.history = self._load_history()

    def _clean_reply(self, text):
        """清理回复中的Markdown格式符号"""
        # 从配置文件中获取需要清理的符号
        cleanup_chars = self.config.get('cleanup_chars', [])

        for char in cleanup_chars:
            text = text.replace(char, "")

        # 清理多余的空白行
        text = re.sub(r'\n\s*\n', '\n', text)

        return text.strip()
    def _load_history(self):
        """加载历史记录"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"FUCKING ERROR 加载历史记录出错: {e}")
        return {}

    def _save_history(self):
        """保存历史记录"""
        try:
            # 确保目录存在
            history_dir = os.path.dirname(self.history_file)
            os.makedirs(history_dir, exist_ok=True)

            # 确保文件存在
            if not os.path.exists(self.history_file):
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=2)  # type: ignore

            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)  # type: ignore
        except Exception as e:
            print(f"FUCKING ERROR 保存历史记录出错: {e}")

    def get_user_history(self, user_id):
        """获取用户的历史记录（公共接口）"""
        return self._get_user_history(user_id)
    def _get_user_history(self, user_id):
        """获取用户的历史记录"""
        return self.history.get(str(user_id), [])

    def _update_user_history(self, user_id, message):
        """更新用户的历史记录"""
        try:
            # 确保用户历史记录存在
            user_id = str(user_id)
            if user_id not in self.history:
                self.history[user_id] = []

            self.history[user_id].append(message)
            # 保持历史记录长度在设定范围内，默认为 10 条
            max_length = self.config.get('memory_length', 10)
            if len(self.history[user_id]) > max_length:
                self.history[user_id] = self.history[user_id][-max_length:]

            # 异步保存历史记录，避免阻塞主流程
            self._save_history()
        except Exception as e:
            print(f"更新用户历史记录时出错: {e}")

    def _save_conversation_to_history(self, msg, user_input, reply, is_image=False):
        """保存对话到历史记录"""
        if hasattr(msg, 'user_id'):
            # 如果是图片消息，将用户输入标记为"图片"
            user_content = "[用户发送了一张图片]" if is_image else user_input
            self._update_user_history(msg.user_id, {"role": "user", "content": user_content})
            # 确保回复内容不为空再保存
            if reply:
                self._update_user_history(msg.user_id, {"role": "assistant", "content": reply})

    def _build_vision_messages(self, image_data: str, prompt: str = "请描述这张图片"):
        """构建图像识别消息列表"""
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

    def _encode_image_from_url(self, image_url: str) -> str:
        """从URL获取图片并编码为base64"""
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            return base64.b64encode(response.content).decode('utf-8')
        except Exception as e:
            raise Exception(f"获取或编码图片失败: {str(e)}")

    def _handle_model_error(self, error):
        """处理模型错误的通用方法"""
        error_str = str(error)
        if "401" in error_str or "Unauthorized" in error_str:
            return "模型API认证失败，请检查配置文件"
        elif "500" in error_str:
            return "模型服务 500 错误，服务器内部错误，请检查云端大模型是否具备 MCP 功能"
        elif "502" in error_str:
            return "LLM 请求失败，请检查大模型是否开启"
        elif "timeout" in error_str.lower() or "time out" in error_str.lower():
            return "请求超时，请稍后重试"
        else:
            return f"请求出错了：{error_str}"

    async def recognize_image_with_prompt(self, image_url: str, prompt: str = "请描述这张图片"):
        """使用视觉模型识别图片并结合用户问题"""
        raise NotImplementedError("子类必须实现 recognize_image_with_prompt 方法")

    async def useModel(self, msg: GroupMessage, user_input: str):
        """使用模型处理消息"""
        raise NotImplementedError("子类必须实现 useModel 方法")

    async def clear_user_history(self, user_id: str):
        """清除指定用户的历史记录"""
        user_id = str(user_id)
        if user_id in self.history:
            del self.history[user_id]
            self._save_history()
            reply = "已清空聊天记录"
        else:
            reply = "没有找到用户的聊天记录"
        return reply


class ChatModelLangchain(BaseChatModel):
    def __init__(self, plugin_dir):
        """使用Langchain初始化参数"""
        super().__init__(plugin_dir)

        # 初始化 Langchain ChatOpenAI 客户端
        self.client = ChatOpenAI(
            model_name=self.config["model"],
            temperature=self.config.get("model_temperature", 0.6),
            openai_api_key=self.config["api_key"],
            openai_api_base=self.config["base_url"],
        )

        # 初始化视觉模型客户端
        self.vision_client = ChatOpenAI(
            model_name=self.config.get("vision_model"),
            openai_api_key=self.config.get("vision_api_key", self.config["api_key"]),
            openai_api_base=self.config.get("vision_base_url"),
        )

        # MCP 客户端设置
        self.mcp_client = None
        self.mcp_tools = []
        self.graph = None

        mcp_config_file = os.path.join(plugin_dir, "mcp_config.json")
        if os.path.exists(mcp_config_file):
            try:
                with open(mcp_config_file, "r", encoding="utf-8") as f:
                    mcp_config = json.load(f).get("mcpServers", {})
                if mcp_config:
                    self.mcp_client = MultiServerMCPClient(mcp_config)
            except Exception as e:
                print(f"加载 MCP 配置失败: {e}")
        else:
            print("未找到 mcp_config.json 文件，MCP 功能将不可用")

        # 内存
        self.user_histories = {}

    async def _init_graph(self):
        """初始化 LangGraph + MCP 工具"""
        if self.graph:
            return self.graph

        tools = []
        if self.mcp_client:
            try:
                tools = await self.mcp_client.get_tools()
                print(f"已加载 {len(tools)} 个 MCP 工具")
            except Exception as e:
                error_str = str(e)
                if "Missing 'transport' key" in error_str:
                    print("MCP配置错误: 请在mcp_config.json中为每个服务器配置添加'transport'字段。可选值: 'stdio', 'sse', 'websocket', 'streamable_http'")
                else:
                    print(f"MCP 工具加载失败: {e}")

        # 若模型不支持 tools，就不要 bind_tools
        model_with_tools = self.client
        tool_node = None
        if tools:
            try:
                # 尝试绑定，如果失败就退回原始模型
                model_with_tools = self.client.bind_tools(tools)
                tool_node = ToolNode(tools)
            except Exception as e:
                print(f"模型不支持 tools，使用原始模型: {e}")
                model_with_tools = self.client
                tool_node = ToolNode(tools)

        async def call_model(state: MessagesState):
            messages = state["messages"]
            # 在消息列表开头添加系统提示词
            system_prompt_manager = SystemPromptManager(self.plugin_dir)
            system_prompt = system_prompt_manager.get_system_prompt()
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                messages = [SystemMessage(content=system_prompt)] + messages
            print(f"{system_prompt}")
            response = await model_with_tools.ainvoke(messages)
            return {"messages": [response]}

        def should_continue(state: MessagesState):
            last_message = state["messages"][-1]
            # 检查是否有工具调用
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tools" if tool_node else END
            # 如果没有工具调用，直接结束
            return END

        builder = StateGraph(MessagesState)         # type: ignore
        builder.add_node("call_model", call_model)  # type: ignore
        if tool_node:
            builder.add_node("tools", tool_node)

        builder.add_edge(START, "call_model")
        builder.add_conditional_edges(
            "call_model",
            should_continue,
            {
                "tools": "tools" if tool_node else END,
                END: END,
            }
        )
        if tool_node:
            builder.add_edge("tools", "call_model")

        self.graph = builder.compile()
        return self.graph

    async def recognize_image_with_prompt(self, image_url: str, prompt: str = "请描述这张图片"):
        """使用视觉模型识别图片并结合用户问题"""
        try:
            # 获取并编码图片
            image_data = self._encode_image_from_url(image_url)

            # 构建包含图片和用户问题的消息
            messages = self._build_vision_messages(image_data, prompt)

            # 调用视觉模型
            response = self.vision_client.invoke(messages)

            reply = self._clean_reply(response.content)
            return reply
        except Exception as e:
            # 检查是否是认证错误
            error_str = str(e)
            if "401" in error_str or "Unauthorized" in error_str:
                raise Exception("模型API认证失败，请检查配置文件")
            raise Exception(f"图像识别出错: {error_str}")

    async def useModel(self, msg: GroupMessage, user_input: str):
        """使用 LangChain + MCP 处理消息"""
        try:
            graph = await self._init_graph()


            # 构建包含历史记录的消息
            messages = []

            # 添加历史记录
            if hasattr(msg, 'user_id'):
                history = self._get_user_history(msg.user_id)
                for item in history:
                    if item["role"] == "user":
                        # 确保用户消息内容有效
                        if item.get("content"):
                            messages.append(HumanMessage(content=item["content"]))
                    elif item["role"] == "assistant":
                        # 确保助手消息内容有效
                        if item.get("content"):
                            messages.append(AIMessage(content=item["content"]))
                    # system message 会在 call_model 中添加

            # 添加当前用户输入
            messages.append(HumanMessage(content=user_input))

            # 传入包含历史记录的 LangChain 消息对象
            response = await graph.ainvoke(
                {"messages": messages}  # type: ignore
            )

            reply = self._clean_reply(response["messages"][-1].content)
            self._save_conversation_to_history(msg, user_input, reply)

        except Exception as e:
            # 使用通用错误处理方法
            reply = self._handle_model_error(e)
        return reply


class ChatModel(BaseChatModel):
    def __init__(self, config_path):
        """初始化参数"""
        super().__init__(config_path)

        # 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=self.config['api_key'],
            base_url=self.config['base_url']
        )

        # 初始化视觉模型客户端（用于图像识别）
        self.vision_client = OpenAI(
            api_key=self.config.get('vision_api_key', self.config['api_key']),
            base_url=self.config.get('vision_base_url')
        )

    def _build_messages(self, user_input: str, user_id: str = None):
        """构建消息列表"""
        messages = []

        # 添加系统提示词
        system_prompt_manager = SystemPromptManager(self.plugin_dir)
        system_prompt = system_prompt_manager.get_system_prompt()
        messages.append({"role": "system", "content": system_prompt})

        if user_id:
            history = self._get_user_history(user_id)
            # 过滤掉无效的历史记录
            for item in history:
                if item["role"] == "assistant" and not item.get("content"):
                    continue
                if item["role"] == "user" and not item.get("content"):
                    continue
                messages.append(item)

        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})
        return messages

    async def recognize_image_with_prompt(self, image_url: str, prompt: str = "请描述这张图片"):
        """使用视觉模型识别图片并结合用户问题"""
        try:
            # 获取并编码图片
            image_data = self._encode_image_from_url(image_url)

            # 构建包含图片和用户问题的消息
            messages = self._build_vision_messages(image_data, prompt)

            # 调用视觉模型
            response = self.vision_client.chat.completions.create(
                model=self.config.get('vision_model'),
                messages=messages,
                temperature=self.config.get('model_temperature', 0.6),
                stream=False,
                max_tokens=2048
            )

            reply = self._clean_reply(response.choices[0].message.content.strip())
            return reply
        except Exception as e:
            # 检查是否是认证错误
            error_str = str(e)
            if "401" in error_str or "Unauthorized" in error_str:
                raise Exception("模型API认证失败，请检查配置文件")
            raise Exception(f"图像识别出错: {error_str}")

    async def useModel(self, msg: GroupMessage, user_input: str):
        """使用模型处理消息，具有记忆能力"""
        try:
            # 构建消息列表，包含历史记录
            messages = self._build_messages(user_input, msg.user_id if hasattr(msg, 'user_id') else None)

            response = self.client.chat.completions.create(
                model=self.config['model'],
                messages=messages,
                temperature=self.config.get('model_temperature', 0.6),
                stream=False
            )
            reply = self._clean_reply(response.choices[0].message.content.strip())

            # 保存当前对话到历史记录
            self._save_conversation_to_history(msg, user_input, reply, is_image=False)

        except Exception as e:
            # 使用通用错误处理方法
            reply = self._handle_model_error(e)
        return reply