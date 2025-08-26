from ncatbot.core import BaseMessage
from ncatbot.utils import config as bot_config
import json, yaml, os

class ConfigManager:
    """配置管理器"""
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.config_path = os.path.join(plugin_dir, 'config.yml')
        self.data_path = os.path.join(plugin_dir, 'data.json')
        
    def get_config_path(self):
        """获取配置文件路径"""
        return self.config_path
        
    def get_data_path(self):
        """获取数据文件路径"""
        return self.data_path
        
    def load_config(self):
        """加载YAML配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"加载配置文件出错: {e}")
            return {}
            
    def load_data(self):
        """加载JSON数据文件"""
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # 如果文件不存在，返回默认数据结构
                return {
                    "banned_groups": [],
                    "banned_users": [],
                    "blocked_words": [],
                    "system_prompt": "你是一个AI助手",
                    "cleanup_chars": [],
                    "admins": []
                }
        except Exception as e:
            print(f"加载数据文件出错: {e}")
            return {
                "banned_groups": [],
                "banned_users": [],
                "blocked_words": [],
                "system_prompt": "你是一个AI助手",
                "cleanup_chars": [],
                "admins": []
            }

    def save_data(self, data):
        """保存数据到JSON文件"""
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2) # type: ignore
        except Exception as e:
            print(f"保存数据文件出错: {e}")


class SystemPromptManager:
    """系统提示词管理器"""
    
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.config_manager = ConfigManager(plugin_dir)
        
    def get_system_prompt(self):
        """获取系统提示词"""
        data = self.config_manager.load_data()
        return data.get("system_prompt", "你是一个AI助手")
        
    def set_system_prompt(self, prompt):
        """设置系统提示词"""
        data = self.config_manager.load_data()
        data["system_prompt"] = prompt
        self.config_manager.save_data(data)
        return True


class ChatUtils:
    """聊天工具类"""
    def __init__(self, plugin_dir):
        # 局部导入
        from .ban import BanManager
        """初始化工具类"""
        self.plugin_dir = plugin_dir
        self.config_manager = ConfigManager(plugin_dir)
        self.ban_manager = BanManager(plugin_dir)
        self.system_prompt_manager = SystemPromptManager(plugin_dir)

    def extract_command_arg(self, text, command_prefix):
        """从消息中提取指令参数"""
        text = text.strip()
        if text.startswith(command_prefix):
            return text[len(command_prefix):].strip()
        return text.strip()

    async def check_ban_and_blocked_words(self, msg: BaseMessage, user_input: str = ""):
        """检查是否被ban或包含违禁词"""
        # 检查是否被ban
        if self.ban_manager.is_banned(msg): # type: ignore
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
            return True

        # 检查用户输入是否包含违禁词
        if user_input and self.ban_manager.check_blocked_words(user_input):
            await msg.reply(text="您的消息包含违禁词，无法处理。")
            return True

        return False

    async def process_image_input(self, msg: BaseMessage, chat_model_instance, user_input: str):
        """处理图像输入"""
        image_url = None
        if hasattr(msg, 'message') and isinstance(msg.message, list):
            for segment in msg.message:
                if isinstance(segment, dict) and segment.get("type") == "image":
                    image_url = segment.get("data", {}).get("url")
                    break

        # 如果是图像消息且开启了图像识别功能，进行图像识别
        if image_url and chat_model_instance.config.get('enable_vision', True):
            # 使用图像识别功能，直接调用视觉模型处理图片和用户问题
            # 如果用户没有发送问题，则默认对图片进行描述
            vision_prompt = user_input if user_input else "请描述这张图片"
            image_description = await chat_model_instance.recognize_image_with_prompt(image_url, vision_prompt)

            # 检查图片描述是否包含违禁词
            if self.ban_manager.check_blocked_words(image_description):
                await msg.reply(text="图片内容包含违禁词，无法处理。")
                return None

            # 直接返回视觉模型的回复，不再进行第二次调用
            return image_description

        elif image_url and not chat_model_instance.config.get('enable_vision', True):
            # 图像识别功能未开启
            user_input = f"用户发送了一张图片，但图像识别功能未开启。用户说：{user_input}"

        return user_input

    async def generate_response(self, msg: BaseMessage, chat_model_instance, user_input: str):
        """生成模型回复"""
        try:
            # 如果user_input已经是视觉模型的回复，则直接返回
            if hasattr(msg, 'message') and isinstance(msg.message, list):
                for segment in msg.message:
                    if isinstance(segment, dict) and segment.get("type") == "image":
                        return user_input if user_input is not None else "抱歉，我无法处理这张图片。"

            # 否则使用普通模型处理
            reply = await chat_model_instance.useModel(msg, user_input)
            
            # 确保回复不是None
            if reply is None:
                reply = "抱歉，我没有理解您的意思。"

        except Exception as e:
            reply = f"抱歉，处理您的请求时出现了错误: {str(e)}"

        return reply

    def is_admin(self, user_id, admins_list):
        """检查用户是否为管理员或超级管理员"""
        return str(user_id) in admins_list or str(user_id) == bot_config.root

    def is_super_admin(self, user_id):
        """检查用户是否为超级管理员"""
        return str(user_id) == bot_config.root

    async def handle_add_clear_word(self, msg: BaseMessage, ban_manager):
        """处理添加输出过滤词"""
        await self.handle_clear_word(msg, ban_manager, is_add=True)

    async def handle_remove_clear_word(self, msg: BaseMessage, ban_manager):
        """处理删除过滤词"""
        await self.handle_clear_word(msg, ban_manager, is_add=False)

    async def handle_clear_word(self, msg: BaseMessage, ban_manager, is_add=True):
        """处理添加/删除输出过滤词的通用方法"""
        # 检查是否为超级管理员
        if not self.is_super_admin(msg.user_id):
            await msg.reply(text="您没有权限执行此操作。")
            return

        # 确定操作类型和指令前缀
        operation = "添加" if is_add else "删除"
        command_prefix = "#add_clear_word" if is_add else "#remove_clear_word"
        handler = ban_manager.add_clear_word if is_add else ban_manager.remove_clear_word

        # 获取过滤词
        text = msg.raw_message.strip()
        word = self.extract_command_arg(text, command_prefix)

        if not word:
            await msg.reply(text=f"请提供要{operation}的过滤词。")
            return

        # 处理过滤词
        result = handler(word)
        if result:
            await msg.reply(text=f"已将过滤词 '{word}' {operation}到列表中。" if is_add 
                              else f"已将过滤词 '{word}' 从列表中{operation}。")
        else:
            await msg.reply(text=f"过滤词 '{word}' 已在列表中。" if is_add 
                              else f"过滤词 '{word}' 不在列表中。")

    async def handle_list_clear_words(self, msg: BaseMessage, ban_manager):
        """处理查看过滤词列表"""
        # 检查是否为超级管理员
        if not self.is_super_admin(msg.user_id):
            await msg.reply(text="您没有权限执行此操作。")
            return

        # 获取过滤词列表
        blocked_words = ban_manager.get_blocked_words()
        if blocked_words:
            word_list = "\n".join(blocked_words)
            reply_text = f"当前过滤词列表：\n{word_list}"
        else:
            reply_text = "当前没有设置过滤词。"
        
        await msg.reply(text=reply_text)

    async def handle_add_admin(self, msg: BaseMessage, admins_list):
        """处理添加管理员（仅限超级管理员）"""
        await self.handle_admin(msg, admins_list, is_add=True)

    async def handle_remove_admin(self, msg: BaseMessage, admins_list):
        """处理删除管理员（仅限超级管理员）"""
        await self.handle_admin(msg, admins_list, is_add=False)

    async def handle_admin(self, msg: BaseMessage, admins_list, is_add=True):
        """处理添加/删除管理员的通用方法"""
        # 检查是否为超级管理员
        if not self.is_super_admin(msg.user_id):
            operation = "添加" if is_add else "删除"
            await msg.reply(text=f"您没有权限执行此操作，仅超级管理员可以{operation}管理员。")
            return

        # 确定操作类型和指令前缀
        operation = "添加" if is_add else "删除"
        command_prefix = "#add_admin" if is_add else "#remove_admin"

        # 获取管理员QQ号
        text = msg.raw_message.strip()
        admin_id = self.extract_command_arg(text, command_prefix)

        if not admin_id:
            await msg.reply(text=f"请提供要{operation}的管理员QQ号。")
            return

        if not admin_id.isdigit():
            await msg.reply(text="管理员QQ号必须为数字。")
            return

        # 检查特殊操作限制
        if is_add and admin_id == bot_config.root:
            await msg.reply(text="超级管理员无需添加到管理员列表。")
            return
        elif not is_add and admin_id == bot_config.root:
            await msg.reply(text="无法删除超级管理员。")
            return

        # 处理管理员列表
        data = self.config_manager.load_data()
        
        if 'admins' not in data:
            data['admins'] = []
            
        is_admin_exists = admin_id in data['admins']
        
        if is_add and not is_admin_exists:
            # 添加管理员
            data['admins'].append(admin_id)
            self.config_manager.save_data(data)
            # 更新传入的admins_list
            admins_list.append(admin_id) if admin_id not in admins_list else None
            await msg.reply(text=f"已将用户 {admin_id} 添加为管理员。")
        elif not is_add and is_admin_exists:
            # 删除管理员
            data['admins'].remove(admin_id)
            self.config_manager.save_data(data)
            # 更新传入的admins_list
            if admin_id in admins_list:
                admins_list.remove(admin_id)
            await msg.reply(text=f"已将用户 {admin_id} 从管理员列表中删除。")
        else:
            # 管理员已存在或不存在的情况
            await msg.reply(text=f"用户 {admin_id} {'已是管理员' if is_add else '不是管理员'}。")

    async def handle_list_admins(self, msg: BaseMessage):
        """处理查看管理员列表"""
        # 检查是否为超级管理员
        if not self.is_super_admin(msg.user_id):
            await msg.reply(text="您没有权限执行此操作。")
            return

        # 获取管理员列表
        data = self.config_manager.load_data()
        data_admins = data.get('admins', [])

        if data_admins:
            admin_list = "\n".join([bot_config.root] + data_admins)  # 包含超级管理员
            reply_text = f"当前管理员列表：\n{admin_list}"
        else:
            reply_text = f"当前管理员列表：\n{bot_config.root} (超级管理员)"
        
        await msg.reply(text=reply_text)
