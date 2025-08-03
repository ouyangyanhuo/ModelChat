from openai import OpenAI
from ollama import chat, ChatResponse
from ncatbot.core import BaseMessage
import json, yaml, os

class ChatModel:
    def __init__(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=self.config['api_key'],
            base_url=self.config['base_url']
        )
        
        # 初始化历史记录存储
        self.history_file = os.path.abspath(os.path.join(os.path.dirname(config_path), './cache/history.json')).replace("\\", "/")
        self.history = self._load_history()

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
        user_id = str(user_id)
        if user_id not in self.history:
            self.history[user_id] = []
        
        self.history[user_id].append(message)
        # 保持历史记录长度在设定范围内，默认为 10 条
        max_length = self.config.get('memory_length', 10)
        if len(self.history[user_id]) > max_length:
            self.history[user_id] = self.history[user_id][-max_length:]
        
        self._save_history()


    def _build_messages(self, user_input: str, user_id: str = None, isMemory =  False):
        """构建消息列表"""
        messages = []
        
        # 添加系统提示词
        system_prompt = self.config.get('system_prompt', "你是一名聊天陪伴机器人")
        messages.append({"role": "system", "content": system_prompt})

        if user_id and isMemory:
            history = self._get_user_history(user_id)
            messages.extend(history)
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})
        return messages


    async def useCloudModel(self, msg: BaseMessage, user_input: str):
        """使用云端模型处理消息，具有记忆能力"""
        try:
            # 构建消息列表，包含历史记录
            messages = self._build_messages(user_input, msg.user_id if hasattr(msg, 'user_id') else None, True)
            
            response = self.client.chat.completions.create(
                model=self.config['model'],
                messages=messages,
                temperature=0.7,
                stream=False
            )
            reply = response.choices[0].message.content.strip()
            
            # 保存当前对话到历史记录
            if hasattr(msg, 'user_id'):
                self._update_user_history(msg.user_id, {"role": "user", "content": user_input})
                self._update_user_history(msg.user_id, {"role": "assistant", "content": reply})
            
        except Exception as e:
            reply = f"请求出错了：{str(e)}"
        return reply

    async def useLocalModel(self, msg: BaseMessage, user_input: str):
        """使用本地模型处理消息"""
        try:
            # 构建消息列表，包含历史记录
            messages = self._build_messages(user_input, msg.user_id if hasattr(msg, 'user_id') else None, True)
            response: ChatResponse = chat(
                model=self.config['model'],
                messages=messages
            )
            reply = response.message.content.strip()

            # 保存当前对话到历史记录
            if hasattr(msg, 'user_id'):
                self._update_user_history(msg.user_id, {"role": "user", "content": user_input})
                self._update_user_history(msg.user_id, {"role": "assistant", "content": reply})
        except Exception as e:
            reply = f"请求出错了：{str(e)}"
        return reply
