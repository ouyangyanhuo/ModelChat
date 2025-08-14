from openai import OpenAI
from ollama import chat, ChatResponse
from ncatbot.core import GroupMessage
import json, yaml, os, requests, base64

# 添加MCP相关导入
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    print("MCP库未安装，MCP功能将不可用")

class ChatModel:
    def __init__(self, config_path):
        """初始化参数"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

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
        
        # 初始化历史记录存储
        self.history_file = os.path.abspath(os.path.join(os.path.dirname(config_path), './cache/history.json')).replace("\\", "/")
        self.history = self._load_history()
        
        # 初始化违禁词列表
        self.blocklist_file = os.path.abspath(os.path.join(os.path.dirname(config_path), 'blocklist.json'))
        self.blocklist = self._load_blocklist()
        
        # 初始化MCP配置
        self.mcp_enabled = self.config.get('enable_mcp', False) and HAS_MCP
        print(f"MCP enabled in config: {self.config.get('enable_mcp', False)}")
        print(f"HAS_MCP: {HAS_MCP}")
        print(f"Initial mcp_enabled: {self.mcp_enabled}")
        
        if self.mcp_enabled:
            self.mcp_config = self._load_mcp_config(config_path)
            print(f"MCP config loaded: {self.mcp_config}")
            # 如果启用了MCP但配置不可用，则禁用MCP功能
            if self.mcp_config is None:
                self.mcp_enabled = False
                print("MCP功能已启用但未找到配置文件，请创建 mcp_config.yml 文件")
            else:
                print("MCP功能已启用且配置文件已加载")
        else:
            self.mcp_config = None
            print("MCP功能未启用或MCP库未安装")

    def _load_mcp_config(self, config_path):
        """加载MCP配置"""
        mcp_config_path = os.path.join(os.path.dirname(config_path), 'mcp_config.yml')
        try:
            if os.path.exists(mcp_config_path):
                with open(mcp_config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            else:
                # 如果配置文件不存在，返回None
                return None
        except Exception as e:
            print(f"加载MCP配置出错: {e}")
            return None

    def _load_blocklist(self):
        """加载违禁词列表"""
        try:
            if os.path.exists(self.blocklist_file):
                with open(self.blocklist_file, 'r', encoding='utf-8') as f:
                    blocklist_data = json.load(f)
                    # 确保返回的是列表
                    if isinstance(blocklist_data, list):
                        return blocklist_data
        except Exception as e:
            print(f"加载违禁词列表出错: {e}")
        return []

    def _check_blocked_words(self, text):
        """检查文本是否包含违禁词"""
        for block_word in self.blocklist:
            if block_word in text:
                return True
        return False

    def _clean_reply(self, text):
        """清理回复中的Markdown格式符号"""
        # 从配置文件中获取需要清理的符号
        cleanup_chars = self.config.get('cleanup_chars', [
            "**",  # 粗体符号
            "#"    # 标题符号
        ])
        
        for char in cleanup_chars:
            text = text.replace(char, "")
        
        return text

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
            if not os.path.exists(history_dir):
                os.makedirs(history_dir)
            
            # 确保文件存在
            if not os.path.exists(self.history_file):
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=2)
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"FUCKING ERROR 保存历史记录出错: {e}")

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

    def _save_conversation_to_history(self, msg, user_input, reply):
        """保存对话到历史记录"""
        if hasattr(msg, 'user_id'):
            self._update_user_history(msg.user_id, {"role": "user", "content": user_input})
            self._update_user_history(msg.user_id, {"role": "assistant", "content": reply})

    def _build_messages(self, user_input: str, user_id: str = None):
        """构建消息列表"""
        messages = []
        
        # 添加系统提示词
        system_prompt = self.config.get('system_prompt', "你是一名聊天陪伴机器人")
        messages.append({"role": "system", "content": system_prompt})

        if user_id:
            history = self._get_user_history(user_id)
            messages.extend(history)
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})
        return messages

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

    async def recognize_image(self, image_url: str, prompt: str = "请描述这张图片"):
        """使用云端视觉模型识别图片"""
        try:
            # 获取并编码图片
            image_data = self._encode_image_from_url(image_url)
            
            # 构建消息
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
            if "401" in str(e) or "Unauthorized" in str(e):
                raise Exception("模型API认证失败，请检查配置文件")
            # 如果图像识别失败，尝试使用备用方法
            try:
                # 使用简化格式
                messages = [
                    {
                        "role": "user",
                        "content": f"{prompt}"
                    }
                ]
                
                response = self.vision_client.chat.completions.create(
                    model=self.config.get('vision_model'),
                    messages=messages,
                    temperature=self.config.get('model_temperature', 0.6),
                    stream=False,
                    max_tokens=2048
                )
                
                reply = self._clean_reply(f"图片识别功能暂时不可用，但用户发送了图片。{response.choices[0].message.content.strip()}")
                return reply
            except Exception as fallback_error:
                # 检查备用方法是否也是认证错误
                if "401" in str(fallback_error) or "Unauthorized" in str(fallback_error):
                    raise Exception("模型API认证失败，请检查配置文件")
                raise Exception(f"图像识别出错: {str(e)}, 备用方法也失败: {str(fallback_error)}")

    async def useCloudModel(self, msg: GroupMessage, user_input: str):
        """使用云端模型处理消息，具有记忆能力"""
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
            self._save_conversation_to_history(msg, user_input, reply)
            
        except Exception as e:
            # 检查是否是认证错误
            if "401" in str(e) or "Unauthorized" in str(e):
                reply = "模型API认证失败，请检查配置文件"
            else:
                reply = f"请求出错了：{str(e)}"
        return reply

    async def useLocalModel(self, msg: GroupMessage, user_input: str):
        """使用本地模型处理消息"""
        try:
            # 构建消息列表，包含历史记录
            messages = self._build_messages(user_input, msg.user_id if hasattr(msg, 'user_id') else None)
            response: ChatResponse = chat(
                model=self.config['model'],
                messages=messages
            )
            reply = self._clean_reply(response.message.content.strip())

            # 保存当前对话到历史记录
            self._save_conversation_to_history(msg, user_input, reply)
        except Exception as e:
            reply = f"请求出错了：{str(e)}"
        return reply

    async def useMCPModel(self, msg: GroupMessage, user_input: str):
        """使用MCP模型处理消息"""
        print(f"useMCPModel called with input: {user_input}")
        
        if not self.mcp_enabled:
            print("MCP not enabled, returning")
            return "MCP功能未启用或未安装相关依赖"
        
        if not self.mcp_config:
            print("MCP config not found, returning")
            return "未找到MCP配置文件，请创建 mcp_config.yml 文件配置MCP服务"
        
        print(f"MCP config: {self.mcp_config}")
        
        try:
            # 获取默认MCP服务配置
            default_mcp_name = self.mcp_config.get('default_mcp')
            mcp_servers = self.mcp_config.get('mcp_servers', {})
            
            print(f"Default MCP name: {default_mcp_name}")
            print(f"MCP servers: {mcp_servers}")
            
            if not default_mcp_name:
                return "未指定默认MCP服务，请在 mcp_config.yml 中设置 default_mcp"
            
            if default_mcp_name not in mcp_servers:
                return f"未找到名为 {default_mcp_name} 的MCP服务"
            
            mcp_server_config = mcp_servers[default_mcp_name]
            if not mcp_server_config.get('enabled', False):
                return f"MCP服务 {default_mcp_name} 未启用"
            
            # 构建消息列表，包含历史记录
            messages = self._build_messages(user_input, msg.user_id if hasattr(msg, 'user_id') else None)
            
            # 根据MCP服务类型进行连接
            mcp_type = mcp_server_config.get('type', 'stdio')
            
            print(f"MCP type: {mcp_type}")
            
            if mcp_type == 'stdio':
                command = mcp_server_config.get('command')
                args = mcp_server_config.get('args', [])
                
                print(f"Command: {command}")
                print(f"Args: {args}")
                
                if not command:
                    return "MCP服务器配置不正确：缺少命令"
                
                # 使用MCP客户端与服务器通信
                # 注意：StdioServerParameters需要command是字符串，args是列表
                try:
                    async with stdio_client(StdioServerParameters(command=command, args=args)) as (read, write):
                        async with ClientSession(read, write) as session:
                            # 先列出工具看看MCP服务是否正常工作
                            try:
                                tools_result = await session.list_tools()
                                available_tools = [tool.name for tool in tools_result.tools]
                                print(f"Available tools: {available_tools}")
                                
                                # 根据可用工具选择合适的调用方式
                                if "查询12306购票信息" in available_tools and any(keyword in user_input for keyword in ["火车票", "车次", "余票", "12306"]):
                                    # 对于12306相关查询，使用专用工具
                                    result = await session.call_tool("查询12306购票信息", {"prompt": user_input})
                                else:
                                    # 使用通用聊天工具
                                    result = await session.call_tool("chat", {"messages": messages})
                                    
                            except Exception as tools_error:
                                print(f"List tools error: {tools_error}")
                                # 如果无法列出工具，直接尝试使用chat工具
                                result = await session.call_tool("chat", {"messages": messages})
                            
                            if result and hasattr(result, 'content'):
                                reply = self._clean_reply(str(result.content))
                            elif result and hasattr(result, 'text'):
                                reply = self._clean_reply(str(result.text))
                            else:
                                reply = "MCP服务器未返回有效响应"
                except Exception as client_error:
                    print(f"Client connection error: {client_error}")
                    import traceback
                    traceback.print_exc()
                    return f"MCP客户端连接出错：{str(client_error)}"
                            
            elif mcp_type == 'http':
                # HTTP类型的MCP服务支持（占位）
                url = mcp_server_config.get('url')
                if not url:
                    return "MCP服务器配置不正确：缺少URL"
                reply = "HTTP类型的MCP服务暂未实现"
            else:
                return f"不支持的MCP服务类型: {mcp_type}"
            
            # 保存当前对话到历史记录
            self._save_conversation_to_history(msg, user_input, reply)
            
        except Exception as e:
            print(f"MCP error: {str(e)}")
            import traceback
            traceback.print_exc()
            reply = f"MCP请求出错了：{str(e)}"
        return reply

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
