from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core import BaseMessage, GroupMessage
from ncatbot.utils import config as bot_config
from .chat import ChatModel, ChatModelLangchain
from .utils import ChatUtils, SystemPromptManager, ConfigManager
from .ban import BanManager
from .commands import USER_COMMANDS, ADMIN_COMMANDS, SUPER_ADMIN_ONLY_COMMANDS
import os,yaml

bot = CompatibleEnrollment  # 兼容回调函数注册器

# 根据配置决定使用哪个模型类
plugin_dir = os.path.dirname(__file__)
config_path = os.path.join(plugin_dir, 'config.yml')
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 使用ConfigManager加载data.json中的配置
config_manager = ConfigManager(plugin_dir)
data_config = config_manager.load_data()

# 检查是否启用MCP系统
if config.get('enable_mcp', True):
    chat_model_instance = ChatModelLangchain(plugin_dir)  # 使用Langchain实现
    print("MCP 已启用")
else:
    chat_model_instance = ChatModel(plugin_dir)  # 使用原始实现（兼容性更好）
    print("MCP 已禁用")

chat_utils = ChatUtils(plugin_dir)  # 创建 ChatUtils 实例
ban_manager = BanManager(plugin_dir)  # 创建 BanManager 实例


class ModelChat(BasePlugin):
    name = "ModelChat"
    version = "2.1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 用于存储指令
        self.commands = []
        self.admin_commands = []
        # 仅超级管理员可执行的操作
        self.super_admin_only_commands = SUPER_ADMIN_ONLY_COMMANDS
        # 用于跟踪处于对话模式中的用户
        self.active_chats = set()
        # 聊天模型配置
        self.chat_model = {}

    def _check_active_chat(self, msg):
        """检查并处理用户处于持续对话模式的情况"""
        if msg.user_id in self.active_chats:
            print(f"收到用户 {msg.user_id} 的消息，但处于持续对话模式中，拒绝调用该功能。")
            return True
        return False

    async def on_load(self):
        # 插件加载提示
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        # 读取配置文件
        with open(config_path, 'r', encoding='utf-8') as config_file:
            self.chat_model = yaml.safe_load(config_file)
            
        # 从data.json加载admins配置
        self.chat_model['admins'] = data_config.get('admins', [])
            
        # 注册指令
        self.commands = USER_COMMANDS
        self.admin_commands = ADMIN_COMMANDS
            
        # 实际注册指令
        for cmd in self.commands:
            self.register_user_func(
                name=cmd["name"],
                handler=getattr(self, cmd["handler"]),
                prefix=cmd["prefix"]
            )
            
        # 注册管理员指令
        for cmd in self.admin_commands:
            self.register_user_func(
                name=cmd["name"],
                handler=getattr(self, cmd["handler"]),
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
            if await chat_utils.check_ban_and_blocked_words(msg, user_input):
                print("被 ban 或存在违禁词，被移出持续对话模式")
                # 从活动对话中移除被ban的用户
                self.active_chats.discard(msg.user_id)
                return

            print("正在向LLM发送聊天请求[持续模式]")
            # 处理图像输入
            processed_input = await chat_utils.process_image_input(msg, chat_model_instance, user_input)
            if processed_input is None:  # 图片包含违禁词
                return

            # 生成回复
            reply = await chat_utils.generate_response(msg, chat_model_instance, processed_input)

            await msg.reply(text=reply)

    async def start_chat(self, msg: BaseMessage):
        """开始持续对话模式"""
        if not chat_model_instance.config['enable_continuous_session']:
            await msg.reply(text="持续对话功能已禁用")
            return

        print(f"收到开始对话请求，用户ID: {msg.user_id}")
        
        # 检查是否被ban
        if ban_manager.is_banned(msg): # type: ignore
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
        history = chat_model_instance.get_user_history(msg.user_id)
        if history:
            reply = "已加载之前的对话记录，现在您可以开始对话了！"
        else:
            reply = "已进入持续对话模式，现在您可以开始对话了！输入 #stop_chat 结束对话。"
        
        await msg.reply(text=reply)

    async def stop_chat(self, msg: BaseMessage):
        """结束持续对话模式"""
        if not chat_model_instance.config['enable_continuous_session']:
            await msg.reply(text="持续对话功能已禁用")
            return

        # 从活动对话集合中移除用户
        if msg.user_id in self.active_chats:
            self.active_chats.discard(msg.user_id)
            print(f"[User {msg.user_id} 已结束持续模式]")
            reply = "已退出持续对话模式，对话历史已保存。"
        else:
            reply = "您当前未处于持续对话模式中。输入 #chat 开始对话。"
            
        await msg.reply(text=reply)

    async def chat(self, msg: BaseMessage):
        # 检查是否处于持续对话模式中
        if self._check_active_chat(msg):
            return

        text = msg.raw_message.strip()
        user_input = text[3:].strip() if text.startswith('#chat') else text[5:].strip()

        # 检查是否被ban或包含违禁词
        if await chat_utils.check_ban_and_blocked_words(msg, user_input):
            print("被 ban 或存在违禁词，拒绝发送请求")
            return

        print("正在向LLM发送聊天请求")
        # 处理图像输入
        processed_input = await chat_utils.process_image_input(msg, chat_model_instance, user_input)
        if processed_input is None:  # 图片包含违禁词
            return

        # 生成回复
        reply = await chat_utils.generate_response(msg, chat_model_instance, processed_input)

        # 确保回复不是None
        if reply is None:
            reply = "抱歉，我没有理解您的意思。"

        # 回复消息
        await msg.reply(text=reply)

    async def chat_history(self, msg: BaseMessage):
        # 检查是否被ban
        if ban_manager.is_banned(msg): # type: ignore
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
            return

        reply = await chat_model_instance.clear_user_history(msg.user_id) # type: ignore
        await msg.reply(text=reply)
    async def ban_manager(self, msg: GroupMessage):
        """管理ban列表的指令"""
        await self._handle_ban_unban_command(msg, is_ban=True)

    async def unban_manager(self, msg: GroupMessage):
        """管理unban列表的指令"""
        await self._handle_ban_unban_command(msg, is_ban=False)

    async def _handle_ban_unban_command(self, msg: GroupMessage, is_ban=True):
        """处理ban/unban命令的通用函数"""
        # 检查是否处于持续对话模式中
        if self._check_active_chat(msg):
            return

        # 使用ban_manager处理命令
        if is_ban:
            reply_text, should_return = ban_manager.handle_ban_command(
                msg, 
                self.chat_model.get('admins', []),
            )
        else:
            reply_text, should_return = ban_manager.handle_unban_command(
                msg, 
                self.chat_model.get('admins', []),
            )
        
        # 如果需要提前返回（如被ban或无权限）
        if should_return:
            await msg.reply(text=reply_text)
            return
            
        # 发送回复
        await msg.reply(text=reply_text)

    async def system_prompt_handler(self, msg: GroupMessage):
        """处理系统提示词修改指令"""
        # 检查是否处于持续对话模式中
        if self._check_active_chat(msg):
            return

        # 检查是否为超级管理员（参考ban.py的实现方式）
        if str(msg.user_id) != bot_config.root:
            await msg.reply(text="您没有权限执行此操作，仅超级管理员可以修改系统提示词。")
            return

        # 检查是否被ban
        if ban_manager.is_banned(msg):
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
            return

        # 获取新的系统提示词
        text = msg.raw_message.strip()
        new_prompt = chat_utils.extract_command_arg(text, "#system_prompt")

        if not new_prompt:
            # 如果没有提供新的提示词，则显示当前提示词
            system_prompt_manager = SystemPromptManager(os.path.dirname(__file__))
            current_prompt = system_prompt_manager.get_system_prompt()
            await msg.reply(text=f"当前系统提示词：{current_prompt}")
            return

        # 更新系统提示词
        system_prompt_manager = SystemPromptManager(os.path.dirname(__file__))
        system_prompt_manager.set_system_prompt(new_prompt)
        await msg.reply(text=f"已更新系统提示词为：{new_prompt}")

    def _format_command_info(self, cmd):
        """格式化命令信息"""
        menu_text = f"指令: {cmd.get('prefix', 'N/A')}\n"
        menu_text += f"描述: {cmd.get('description', '暂无描述')}\n"

        examples = cmd.get('examples', [])
        if examples:
            menu_text += "示例:\n"
            for example in examples:
                menu_text += f"  - {example}\n"
        else:
            menu_text += "示例: 暂无示例\n"

        menu_text += "\n"
        return menu_text

    async def chat_menu(self, msg: BaseMessage):
        """显示聊天菜单"""
        # 检查是否处于持续对话模式中
        if self._check_active_chat(msg):
            return

        # 检查是否被ban
        if ban_manager.is_banned(msg): # type: ignore
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
            return

        menu_text = "===== 大模型聊天 =====\n\n"

        # 判断是否为管理员或超级管理员（参考ban.py的实现方式）
        is_admin = str(msg.user_id) in self.chat_model.get('admins', []) or str(msg.user_id) == bot_config.root

        # 添加普通命令
        for cmd in self.commands:
            # 跳过菜单本身
            if cmd.get('prefix') == "聊天菜单":
                continue
            menu_text += self._format_command_info(cmd)

        # 如果是管理员或超级管理员，添加管理员命令
        if is_admin:
            for cmd in self.admin_commands:
                # 特殊处理仅超级管理员可执行的命令
                if cmd.get('name') in self.super_admin_only_commands:
                    if str(msg.user_id) == bot_config.root:
                        menu_text += self._format_command_info(cmd)
                else:
                    menu_text += self._format_command_info(cmd)

        menu_text += "========================"
        await msg.reply(text=menu_text)

    async def add_clear_word(self, msg: GroupMessage):
        """添加过滤词"""
        # 检查是否处于持续对话模式中
        if self._check_active_chat(msg):
            return

        await chat_utils.handle_add_clear_word(msg, ban_manager)

    async def remove_clear_word(self, msg: GroupMessage):
        """删除过滤词"""
        # 检查是否处于持续对话模式中
        if self._check_active_chat(msg):
            return

        await chat_utils.handle_remove_clear_word(msg, ban_manager)

    async def list_clear_words(self, msg: GroupMessage):
        """查看过滤词列表"""
        # 检查是否处于持续对话模式中
        if self._check_active_chat(msg):
            return

        await chat_utils.handle_list_clear_words(msg, ban_manager)

    async def add_admin(self, msg: GroupMessage):
        """添加管理员（仅限超级管理员）"""
        # 检查是否处于持续对话模式中
        if self._check_active_chat(msg):
            return

        await chat_utils.handle_add_admin(msg, self.chat_model.get('admins', []))

    async def remove_admin(self, msg: GroupMessage):
        """删除管理员（仅限超级管理员）"""
        # 检查是否处于持续对话模式中
        if self._check_active_chat(msg):
            return

        await chat_utils.handle_remove_admin(msg, self.chat_model.get('admins', []))

    async def list_admins(self, msg: GroupMessage):
        """查看管理员列表"""
        # 检查是否处于持续对话模式中
        if self._check_active_chat(msg):
            return

        await chat_utils.handle_list_admins(msg)
