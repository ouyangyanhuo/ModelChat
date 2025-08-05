from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core import BaseMessage, GroupMessage
from .chat import ChatModel
from .ban import BanManager
import os, yaml

bot = CompatibleEnrollment  # 兼容注册器
chat_model_instance = ChatModel(os.path.join(os.path.dirname(__file__), 'config.yml'))  # 创建 ChatModel 实例
ban_manager = BanManager(os.path.dirname(__file__))  # 创建 BanManager 实例


class ModelChat(BasePlugin):
    name = "ModelChat"
    version = "1.3.0"

    async def on_load(self):
        # 插件加载提示
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        # 读取配置文件
        config_path = os.path.join(os.path.dirname(__file__), 'config.yml')
        with open(config_path, 'r', encoding='utf-8') as f:
            self.chat_model = yaml.safe_load(f)
        # 注册指令
        self.register_user_func(
            name="ModelChat",
            handler=self.chat,
            prefix="/chat"
        )
        self.register_user_func(
            name="Clear History",
            handler=self.chat_history,
            prefix="/clear chat_history"
        )
        self.register_admin_func(
            name="Ban Manager",
            handler=self.ban_manager,
            prefix="/ban_chat"
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
            if image_url and self.chat_model.get('enable_vision', True) and not self.chat_model.get('use_local_model'):
                # 使用图像识别功能
                image_description = await chat_model_instance.recognize_image(image_url)
                user_input = f"用户发送了一张图片，图片描述是：{image_description}。用户说：{user_input}"

                # 检查图片描述是否包含违禁词
                if ban_manager.check_blocked_words(image_description):
                    await msg.reply(text="图片内容包含违禁词，无法处理。")
                    return
            elif image_url and not self.chat_model.get('enable_vision', True):
                # 图像识别功能未开启,但检测是否是本地模型
                if self.chat_model.get('use_local_model'):
                    user_input = f"用户发送了一张图片，但用户使用的是本地模型，无法进行图像识别。用户说：{user_input}"
                else:
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
        # 检查是否被ban
        if ban_manager.is_banned(msg):
            reply_text = "您或您所在的群组已被禁止使用此功能。"
            await msg.reply(text=reply_text)
            return
            
        # 检查是否为管理员
        admins = self.chat_model.get('admins', [])
        if hasattr(msg, 'user_id') and str(msg.user_id) not in admins:
            reply_text = "您没有权限执行此操作。"
            await msg.reply(text=reply_text)
            return
            
        text = msg.raw_message.strip()
        parts = text.split()
        
        if len(parts) < 3:
            reply_text = "指令格式错误。正确格式：/ban_chat group <群号> 或 /ban_chat user <QQ号>"
        else:
            action = parts[1]  # group 或 user
            target = parts[2]  # 群号或QQ号
            
            if action == "group":
                if ban_manager.add_ban("group", target):
                    reply_text = f"已将群组 {target} 添加到ban列表。"
                else:
                    reply_text = f"群组 {target} 已在ban列表中。"
                    
            elif action == "user":
                if ban_manager.add_ban("user", target):
                    reply_text = f"已将用户 {target} 添加到ban列表。"
                else:
                    reply_text = f"用户 {target} 已在ban列表中。"
                    
            else:
                reply_text = "指令格式错误。正确格式：/ban_chat group <群号> 或 /ban_chat user <QQ号>"
        
        await msg.reply(text=reply_text)
