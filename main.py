from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core import BaseMessage
from .chat import ChatModel
import os

bot = CompatibleEnrollment  # 兼容注册器

class ModelChat(BasePlugin):
    name = "ModelChat"
    version = "1.0.0"

    async def on_load(self):
        print("FUCKING USE ModelChat")
        config_path = os.path.join(os.path.dirname(__file__), 'config.yml')
        self.chat_model = ChatModel(config_path)

        self.register_user_func(
            name="ModelChat",
            handler=self.command,
            prefix="/chat"
        )

    async def command(self, msg: BaseMessage):
        text = msg.raw_message.strip()
        user_input = text[3:].strip()
        print("FUCKING CHAT")

        # 根据配置决定使用本地模型还是云端模型
        if self.chat_model.config['use_local_model']:
            reply = await self.chat_model.useLocalModel(msg, user_input)
        else:
            reply = await self.chat_model.useCloudModel(msg, user_input)

        # 回复消息
        await msg.reply(text=reply)
