from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core import BaseMessage
from .chat import ChatModel
import os,yaml

bot = CompatibleEnrollment  # 兼容注册器
chat_model_instance = ChatModel(os.path.join(os.path.dirname(__file__), 'config.yml'))  # 创建 ChatModel 实例

class ModelChat(BasePlugin):
    name = "ModelChat"
    version = "1.1.0"

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

    async def chat(self, msg: BaseMessage):
        text = msg.raw_message.strip()
        user_input = text[3:].strip()
        print("FUCKING START CHAT")

        # 检查用户输入是否包含违禁词
        if chat_model_instance._check_blocked_words(user_input):
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
                if chat_model_instance._check_blocked_words(image_description):
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
        reply = await chat_model_instance.clear_user_history(msg.user_id)
        await msg.reply(text=reply)
