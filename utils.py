from ncatbot.core import GroupMessage, BaseMessage
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
                json.dump(data, f, ensure_ascii=False, indent=2)
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

    async def check_ban_and_blocked_words(self, msg: BaseMessage, user_input: str = ""):
        """检查是否被ban或包含违禁词"""
        # 检查是否被ban
        if self.ban_manager.is_banned(msg):
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
                        return user_input

            # 否则使用普通模型处理
            reply = await chat_model_instance.useModel(msg, user_input)

        except Exception as e:
            reply = f"{str(e)}"

        return reply

    def is_admin(self, user_id, admins_list):
        """检查用户是否为管理员或超级管理员"""
        return str(user_id) in admins_list or str(user_id) == bot_config.root

    def is_super_admin(self, user_id):
        """检查用户是否为超级管理员"""
        return str(user_id) == bot_config.root

    async def handle_add_clear_word(self, msg: BaseMessage, ban_manager):
        """处理添加输出过滤词"""
        # 检查是否为超级管理员
        if not self.is_super_admin(msg.user_id):
            await msg.reply(text="您没有权限执行此操作。")
            return

        # 获取要添加的过滤词
        text = msg.raw_message.strip()
        if text.startswith("#add_clear_word"):
            word = text[17:].strip()  # 去掉指令部分
        else:
            word = text.strip()

        if not word:
            await msg.reply(text="请提供要添加的过滤词。")
            return

        # 添加过滤词
        result = ban_manager.add_clear_word(word)
        if result:
            await msg.reply(text=f"已将过滤词 '{word}' 添加到列表中。")
        else:
            await msg.reply(text=f"过滤词 '{word}' 已在列表中。")

    async def handle_remove_clear_word(self, msg: BaseMessage, ban_manager):
        """处理删除过滤词"""
        # 检查是否为超级管理员
        if not self.is_super_admin(msg.user_id):
            await msg.reply(text="您没有权限执行此操作。")
            return

        # 获取要删除的过滤词
        text = msg.raw_message.strip()
        if text.startswith("#remove_clear_word"):
            word = text[20:].strip()  # 去掉指令部分
        else:
            word = text.strip()

        if not word:
            await msg.reply(text="请提供要删除的过滤词。")
            return

        # 删除过滤词
        result = ban_manager.remove_clear_word(word)
        if result:
            await msg.reply(text=f"已将过滤词 '{word}' 从列表中删除。")
        else:
            await msg.reply(text=f"过滤词 '{word}' 不在列表中。")

    async def handle_list_blocked_words(self, msg: BaseMessage, ban_manager, admins_list):
        """处理查看过滤词列表"""
        # 检查是否为管理员或超级管理员
        if not self.is_admin(msg.user_id, admins_list):
            await msg.reply(text="您没有权限执行此操作。")
            return

        # 检查是否被ban
        if ban_manager.is_banned(msg):
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
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
        # 检查是否为超级管理员
        if not self.is_super_admin(msg.user_id):
            await msg.reply(text="您没有权限执行此操作，仅超级管理员可以添加管理员。")
            return

        if self.ban_manager.is_banned(msg):
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
            return

        # 获取要添加的管理员QQ号
        text = msg.raw_message.strip()
        if text.startswith("#add_admin"):
            admin_id = text[10:].strip()  # 去掉指令部分
        else:
            admin_id = text.strip()

        if not admin_id:
            await msg.reply(text="请提供要添加的管理员QQ号。")
            return

        if not admin_id.isdigit():
            await msg.reply(text="管理员QQ号必须为数字。")
            return

        # 检查不能将超级管理员添加为普通管理员
        if admin_id == bot_config.root:
            await msg.reply(text="超级管理员无需添加到管理员列表。")
            return

        # 添加管理员
        data = self.config_manager.load_data()
        
        if 'admins' not in data:
            data['admins'] = []
            
        if admin_id not in data['admins']:
            data['admins'].append(admin_id)
            self.config_manager.save_data(data)
            # 更新传入的admins_list
            admins_list.append(admin_id) if admin_id not in admins_list else None
            await msg.reply(text=f"已将用户 {admin_id} 添加为管理员。")
        else:
            await msg.reply(text=f"用户 {admin_id} 已是管理员。")

    async def handle_remove_admin(self, msg: BaseMessage, admins_list):
        """处理删除管理员（仅限超级管理员）"""
        # 检查是否为超级管理员
        if not self.is_super_admin(msg.user_id):
            await msg.reply(text="您没有权限执行此操作，仅超级管理员可以删除管理员。")
            return

        if self.ban_manager.is_banned(msg):
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
            return

        # 获取要删除的管理员QQ号
        text = msg.raw_message.strip()
        if text.startswith("#remove_admin"):
            admin_id = text[13:].strip()  # 去掉指令部分
        else:
            admin_id = text.strip()

        if not admin_id:
            await msg.reply(text="请提供要删除的管理员QQ号。")
            return

        if not admin_id.isdigit():
            await msg.reply(text="管理员QQ号必须为数字。")
            return

        # 检查不能删除超级管理员
        if admin_id == bot_config.root:
            await msg.reply(text="无法删除超级管理员。")
            return

        # 删除管理员
        data = self.config_manager.load_data()
        
        if 'admins' not in data:
            data['admins'] = []
            
        if admin_id in data['admins']:
            data['admins'].remove(admin_id)
            self.config_manager.save_data(data)
            # 更新传入的admins_list
            if admin_id in admins_list:
                admins_list.remove(admin_id)
            await msg.reply(text=f"已将用户 {admin_id} 从管理员列表中删除。")
        else:
            await msg.reply(text=f"用户 {admin_id} 不是管理员。")

    async def handle_list_admins(self, msg: BaseMessage, admins_list):
        """处理查看管理员列表"""
        # 检查是否为管理员或超级管理员
        if not self.is_admin(msg.user_id, admins_list):
            await msg.reply(text="您没有权限执行此操作。")
            return

        if self.ban_manager.is_banned(msg):
            await msg.reply(text="您或您所在的群组已被禁止使用此功能。")
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
