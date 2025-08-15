from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core import BaseMessage, GroupMessage
from .chat import ChatModel, ChatUtils
from .ban import BanManager
import os,yaml

bot = CompatibleEnrollment  # 兼容注册器
chat_model_instance = ChatModel(os.path.join(os.path.dirname(__file__), 'config.yml'))  # 创建 ChatModel 实例
chat_utils = ChatUtils(os.path.join(os.path.dirname(__file__), 'config.yml'))  # 创建 ChatUtils 实例
ban_manager = BanManager(os.path.dirname(__file__))  # 创建 BanManager 实例


class ModelChat(BasePlugin):
    name = "ModelChat"
    version = "1.6.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = []
        # 用于跟踪处于对话模式中的用户
        self.active_chats = set()

    async def on_load(self):
        # 插件加载提示
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        # 读取配置文件
        config_path = os.path.join(os.path.dirname(__file__), 'config.yml')
        with open(config_path, 'r', encoding='utf-8') as f:
            self.chat_model = yaml.safe_load(f)
            
        # 注册指令
        self.commands = [
            {
                "name": "Start Chat",
                "prefix": "/start_chat",
                "handler": self.start_chat,
                "description": "开始持续对话模式",
                "examples": ["/start_chat"]
            },
            {
                "name": "End Chat",
                "prefix": "/stop_chat",
                "handler": self.stop_chat,
                "description": "结束持续对话模式",
                "examples": ["/stop_chat"]
            },
            {
                "name": "ModelChat",
                "prefix": "/chat",
                "handler": self.chat,
                "description": "单次聊天功能",
                "examples": ["/chat <message>","/chat <photo>","/chat <message>+<photo>"]
            },
            {
                "name": "Clear History",
                "prefix": "/clear chat_history",
                "handler": self.chat_history,
                "description": "清除聊天记忆",
                "examples": ["/clear chat_history"]
            },
            {
                "name": "Ban Manager",
                "prefix": "/ban_chat",
                "handler": self.ban_manager,
                "description": "禁止群组/人 使用该插件",
                "examples": ["/ban_chat group <groupID>","/ban_chat user <userID>"]
            },
            {
                "name": "Chat Menu",
                "prefix": "聊天菜单",
                "handler": self.chat_menu,
                "description": "显示聊天插件的使用菜单",
                "examples": ["聊天菜单"]
            }
        ]
        
        # 实际注册指令
        for cmd in self.commands:
            self.register_user_func(
                name=cmd["name"],
                handler=cmd["handler"],
                prefix=cmd["prefix"]
            )

        if chat_model_instance.config['enable_continuous_session']:
            # 注册持续对话模式
            self.register_user_func(
                name="ActiveChatHandler",
                handler=self.active_chat_handler,
                prefix=""
            )
    async def active_chat_handler(self, msg: BaseMessage):
        """处理处于对话模式中的用户消息"""
        # 检查用户是否在对话模式中
        if msg.user_id in self.active_chats:
            user_input = msg.raw_message.strip()
            
            # 检查是否被ban或包含违禁词
            if await chat_utils.check_ban_and_blocked_words(msg, chat_model_instance, user_input):
                # 从活动对话中移除被ban的用户
                self.active_chats.discard(msg.user_id)
                return

            # 处理图像输入
            processed_input = await chat_utils.process_image_input(msg, chat_model_instance, user_input)
            if processed_input is None:  # 图片包含违禁词
                return

            # 生成回复
            reply = await chat_utils.generate_response(msg, chat_model_instance, processed_input)

            # 回复消息
            await msg.reply(text=reply)

    async def start_chat(self, msg: BaseMessage):
        """开始持续对话模式"""
        if not chat_model_instance.config['enable_continuous_session']:
            await msg.reply(text="持续对话功能已禁用")
            return

        print(f"收到开始对话请求，用户ID: {msg.user_id}")
        
        # 检查是否被ban
        if ban_manager.is_banned(msg):
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
            return

        # 将用户添加到活动对话集合中
        if msg.user_id in self.active_chats:
            await msg.reply(text="您已处于持续对话模式中，请勿重复启动。")
            return
        else:
            self.active_chats.add(msg.user_id)
            print(f"用户 {msg.user_id} 已进入对话模式，当前对话用户: {self.active_chats}")
        # 加载用户历史记录
        history = chat_model_instance._get_user_history(msg.user_id)
        if history:
            reply = "已加载之前的对话记录，现在您可以开始对话了！"
        else:
            reply = "已进入持续对话模式，现在您可以开始对话了！输入 /stop_chat 结束对话。"
        
        await msg.reply(text=reply)

    async def stop_chat(self, msg: BaseMessage):
        """结束持续对话模式"""
        if not chat_model_instance.config['enable_continuous_session']:
            await msg.reply(text="持续对话功能已禁用")
            return

        # 从活动对话集合中移除用户
        if msg.user_id in self.active_chats:
            self.active_chats.discard(msg.user_id)
            reply = "已退出持续对话模式，对话历史已保存。"
        else:
            reply = "您当前未处于持续对话模式中。输入 /chat 开始对话。"
            
        await msg.reply(text=reply)

    async def chat(self, msg: BaseMessage):
        # 检查是否处于持续对话模式中
        if msg.user_id in self.active_chats:
            print(f"收到用户 {msg.user_id} 的消息，但处于持续对话模式中，拒绝调用该功能。")
            return

        text = msg.raw_message.strip()
        user_input = text[3:].strip() if text.startswith('/chat') else text[5:].strip()
        print("正在向LLM发送聊天请求")

        # 检查是否被ban或包含违禁词
        if await chat_utils.check_ban_and_blocked_words(msg, chat_model_instance, user_input):
            return

        # 处理图像输入
        processed_input = await chat_utils.process_image_input(msg, chat_model_instance, user_input)
        if processed_input is None:  # 图片包含违禁词
            return

        # 生成回复
        reply = await chat_utils.generate_response(msg, chat_model_instance, processed_input)

        # 回复消息
        await msg.reply(text=reply)

    async def chat_history(self, msg: BaseMessage):
        # 检查是否被ban
        if ban_manager.is_banned(msg):
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
            return

        reply = await chat_model_instance.clear_user_history(msg.user_id)
        await msg.reply(text=reply)

    async def ban_manager(self, msg: GroupMessage):
        """管理ban列表的指令"""
        # 检查是否处于持续对话模式中
        if msg.user_id in self.active_chats:
            print(f"收到用户 {msg.user_id} 的消息，但处于持续对话模式中，拒绝调用该功能。")
            return

        # 使用ban_manager处理命令
        reply_text, should_return = ban_manager.handle_ban_command(
            msg, 
            self.chat_model.get('admins', []), 
            chat_model_instance
        )
        
        # 如果需要提前返回（如被ban或无权限）
        if should_return:
            await msg.reply(text=reply_text)
            return
            
        # 发送回复
        await msg.reply(text=reply_text)

    async def chat_menu(self, msg: BaseMessage):
        """显示聊天菜单"""
        # 检查是否处于持续对话模式中
        if msg.user_id in self.active_chats:
            print(f"收到用户 {msg.user_id} 的消息，但处于持续对话模式中，拒绝调用该功能。")
            return

        # 检查是否被ban
        if ban_manager.is_banned(msg):
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
            return
            
        menu_text = "=== 大模型聊天插件使用菜单 ===\n\n"
        
        # 遍历所有指令信息
        for cmd in self.commands:
            # 跳过菜单本身
            if cmd.get('prefix') == "聊天菜单":
                continue
                
            menu_text += f"指令: {cmd.get('prefix', 'N/A')}\n"
            menu_text += f"描述: {cmd.get('description', '暂无描述')}\n"
            
            examples = cmd.get('examples', [])
            if examples:
                menu_text += "示例:\n"
                for example in examples:
                    menu_text += f"  - {example}\n"
            else:
                menu_text += "示例: 暂无示例\n"
            
            menu_text += "\n"
            
        menu_text += "========================"
        await msg.reply(text=menu_text)
