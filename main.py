from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core import BaseMessage, GroupMessage
from .chat import ChatModel
from .ban import BanManager
import os,yaml

bot = CompatibleEnrollment  # 兼容注册器
chat_model_instance = ChatModel(os.path.join(os.path.dirname(__file__), 'config.yml'))  # 创建 ChatModel 实例
ban_manager = BanManager(os.path.dirname(__file__))  # 创建 BanManager 实例


class ModelChat(BasePlugin):
    name = "ModelChat"
    version = "1.5.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = []

    async def on_load(self):
        # 插件加载提示
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        # 读取配置文件
        config_path = os.path.join(os.path.dirname(__file__), 'config.yml')
        with open(config_path, 'r', encoding='utf-8') as f:
            self.chat_model = yaml.safe_load(f)
        # 注册指令并保存指令信息
        self.commands = [
            {
                "name": "ModelChat",
                "prefix": "/chat",
                "handler": self.chat,
                "description": "聊天功能",
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

    async def chat(self, msg: BaseMessage):
        # 检查是否被ban
        if ban_manager.is_banned(msg):
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
            return
            
        text = msg.raw_message.strip()
        user_input = text[3:].strip()
        print("FUCKING START CHAT")

        # 检查用户输入是否包含违禁词
        if ban_manager.check_blocked_words(user_input):
            await msg.reply(text="您的消息包含违禁词，无法处理。")
            return

        # 检查是否是图像消息
        image_url = None
        if hasattr(msg, 'message') and isinstance(msg.message, list):
            for segment in msg.message:
                if isinstance(segment, dict) and segment.get("type") == "image":
                    image_url = segment.get("data", {}).get("url")
                    break

        try:
            # 如果是图像消息且开启了图像识别功能且不是本地模型，进行图像识别
            if image_url and self.chat_model.get('enable_vision', True):
                # 使用图像识别功能
                image_description = await chat_model_instance.recognize_image(image_url)
                user_input = f"用户发送了一张图片，图片描述是：{image_description}。注意，现在你已经看到图片了，不能回答用户说你没看到图片。用户说：{user_input}。"
                
                # 检查图片描述是否包含违禁词
                if ban_manager.check_blocked_words(image_description):
                    await msg.reply(text="图片内容包含违禁词，无法处理。")
                    return
            elif image_url and not self.chat_model.get('enable_vision', True):
                # 图像识别功能未开启
                user_input = f"用户发送了一张图片，但图像识别功能未开启。用户说：{user_input}"

            # 根据配置决定使用本地模型还是云端模型
            if self.chat_model['use_local_model']:
                reply = await chat_model_instance.useLocalModel(msg, user_input)
            else:
                reply = await chat_model_instance.useCloudModel(msg, user_input)

        except Exception as e:
            reply = f"{str(e)}"

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
