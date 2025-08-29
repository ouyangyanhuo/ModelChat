from .chat import ChatModel, ChatModelLangchain
from .utils import ChatUtils, ConfigManager, SystemPromptManager
import os
import yaml, json

class ModelChatAPI:
    """
    ModelChat插件的API接口，供其他插件调用
    """
    
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        config_path = os.path.join(plugin_dir, 'config.yml')
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 根据配置决定使用哪个模型类
        if self.config.get('enable_mcp', True):
            self.chat_model_instance = ChatModelLangchain(plugin_dir)
            print("MCP 已启用")
        else:
            self.chat_model_instance = ChatModel(plugin_dir)
            print("MCP 已禁用")
            
        self.chat_utils = ChatUtils(plugin_dir)
        self.config_manager = ConfigManager(plugin_dir)
    
    async def generate_response(self, user_id, message, group_id=None):
        """
        生成AI回复的主要API接口
        
        Args:
            user_id (int): 用户ID
            message (str): 用户输入的消息
            group_id (int, optional): 群组ID，如果在群聊中使用
            
        Returns:
            str: AI生成的回复内容
        """
        # 创建一个模拟的消息对象用于API调用
        class MockMessage:
            def __init__(self, user_id, group_id=None):
                self.user_id = user_id
                self.group_id = group_id
                self.raw_message = ""
                self.message = message
        
        mock_msg = MockMessage(user_id, group_id)
        
        # 检查是否被ban或包含违禁词
        if await self.chat_utils.check_ban_and_blocked_words(mock_msg, message):
            return "您或您所在的群组已被禁止使用此功能，或消息包含违禁词。"
        
        # 处理图像输入
        processed_input = await self.chat_utils.process_image_input(mock_msg, self.chat_model_instance, message)
        if processed_input is None:
            return "输入包含违禁内容"
        
        # 生成回复
        try:
            # 如果processed_input已经是视觉模型的回复，则直接返回
            if (hasattr(mock_msg, 'message') and 
                isinstance(mock_msg.message, list) and 
                any(isinstance(segment, dict) and segment.get("type") == "image" 
                    for segment in mock_msg.message)):
                reply = processed_input if processed_input is not None else "抱歉，我无法处理这张图片。"
            else:
                # 否则使用普通模型处理
                reply = await self.chat_model_instance.useModel(mock_msg, processed_input)
                
                # 确保回复不是None
                if reply is None:
                    reply = "抱歉，我没有理解您的意思。"
                    
        except Exception as e:
            reply = f"抱歉，处理您的请求时出现了错误: {str(e)}"
        
        return reply
    
    def get_user_history(self, user_id):
        """
        获取用户历史对话记录
        
        Args:
            user_id (int): 用户ID
            
        Returns:
            list: 历史对话记录
        """
        return self.chat_model_instance.get_user_history(user_id)
    
    def clear_user_history(self, user_id):
        """
        清除用户历史对话记录
        
        Args:
            user_id (int): 用户ID
            
        Returns:
            str: 操作结果
        """
        return self.chat_model_instance.clear_user_history(user_id)
    
    def delete_user_history(self, user_id):
        """
        删除指定用户的历史记录
        
        Args:
            user_id (int): 用户ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            history_file = os.path.join(self.plugin_dir, 'cache', 'history.json')
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                
                user_id_str = str(user_id)
                if user_id_str in history_data:
                    del history_data[user_id_str]
                    
                    with open(history_file, 'w', encoding='utf-8') as f:
                        json.dump(history_data, f, ensure_ascii=False, indent=2)
                    
                    return True
            return True
        except Exception as e:
            print(f"删除用户历史记录时出错: {e}")
            return False

    def get_system_prompt(self):
        """
        获取当前系统提示词
        
        Returns:
            str: 当前系统提示词
        """
        system_prompt_manager = SystemPromptManager(self.plugin_dir)
        return system_prompt_manager.get_system_prompt()
    
    def set_system_prompt(self, prompt):
        """
        设置系统提示词
        
        Args:
            prompt (str): 新的系统提示词
            
        Returns:
            bool: 是否设置成功
        """
        system_prompt_manager = SystemPromptManager(self.plugin_dir)
        system_prompt_manager.set_system_prompt(prompt)
        return True
    
    def get_config(self):
        """
        获取当前配置
        
        Returns:
            dict: 当前配置
        """
        return self.config_manager.load_config_file()

    def update_config(self, updates):
        """
        更新配置文件中的特定键值（保留注释）
        
        Args:
            updates (dict): 需要更新的键值对
            
        Returns:
            bool: 是否更新成功
        """
        return self.config_manager.update_config_file(updates)

    def get_history_sessions(self, allowed_user_ids=None):
        """
        获取历史会话数据
        
        Args:
            allowed_user_ids (list, optional): 允许读取的用户ID列表，如果为None则不限制
            
        Returns:
            dict: 历史会话数据
        """
        return self.config_manager.load_history_sessions(allowed_user_ids)

    def is_admin(self, user_id):
        """
        检查用户是否为管理员
        
        Args:
            user_id (int): 用户ID
            
        Returns:
            bool: 是否为管理员
        """
        data_config = self.config_manager.load_data()
        admins = data_config.get('admins', [])
        return str(user_id) in admins or str(user_id) == self.config.get('root', '')

    def reload_all_configs(self):
        """
        重新加载所有配置并通知相关组件
        
        Returns:
            bool: 是否重新加载成功
        """
        try:
            # 重新加载主配置文件
            with open(self.config_manager.get_config_path(), 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            # 通知chat_model_instance重新加载配置
            if hasattr(self, 'chat_model_instance'):
                self.config_manager.reload_all_configs(self.chat_model_instance)
            
            return True
        except Exception as e:
            print(f"重新加载所有配置出错: {e}")
            return False
