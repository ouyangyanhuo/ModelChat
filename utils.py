from ncatbot.core import GroupMessage, BaseMessage
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