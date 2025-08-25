import json, os
from ncatbot.core import GroupMessage
from ncatbot.utils import config
from .utils import ConfigManager

class BanManager:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.config_manager = ConfigManager(plugin_dir)
        self.banlist_file = self.config_manager.get_data_path()
        self.banlist = self._load_banlist()

    def _load_banlist(self):
        """加载ban列表"""
        try:
            # 通过ConfigManager加载数据
            data = self.config_manager.load_data()
            # 确保所有必要的键都存在
            if "banned_groups" not in data:
                data["banned_groups"] = []
            if "banned_users" not in data:
                data["banned_users"] = []
            if "blocked_words" not in data:
                data["blocked_words"] = []

            return data
        except Exception as e:
            print(f"加载ban列表出错: {e}")
        return {"banned_groups": [], "banned_users": [], "blocked_words": []}

    def _save_banlist(self):
        """保存ban列表"""
        try:
            # 通过ConfigManager保存数据
            self.config_manager.save_data(self.banlist)
        except Exception as e:
            print(f"保存ban列表出错: {e}")

    def is_banned(self, msg: GroupMessage):
        """检查用户或群组是否被ban"""
        # 每次检查时都重新加载最新的ban列表
        latest_banlist = self._load_banlist()

        # 检查用户是否被ban
        if hasattr(msg, 'user_id') and str(msg.user_id) in latest_banlist["banned_users"]:
            return True

        # 检查群组是否被ban
        if hasattr(msg, 'group_id') and str(msg.group_id) in latest_banlist["banned_groups"]:
            return True

        return False

    def check_blocked_words(self, text):
        """检查文本是否包含违禁词"""
        # 每次检查时都重新加载最新的违禁词列表
        latest_banlist = self._load_banlist()

        for block_word in latest_banlist["blocked_words"]:
            if block_word in text:
                return True
        return False

    def add_ban(self, ban_type, target):
        """添加ban项"""
        if ban_type == "group":
            if target not in self.banlist["banned_groups"]:
                self.banlist["banned_groups"].append(target)
                self._save_banlist()
                return True
            return False
        elif ban_type == "user":
            if target not in self.banlist["banned_users"]:
                self.banlist["banned_users"].append(target)
                self._save_banlist()
                return True
            return False
        return False

    def add_blocked_word(self, word):
        """添加违禁词"""
        if word not in self.banlist["blocked_words"]:
            self.banlist["blocked_words"].append(word)
            self._save_banlist()
            return True
        return False

    def remove_ban(self, ban_type, target):
        """移除ban项"""
        if ban_type == "group":
            if target in self.banlist["banned_groups"]:
                self.banlist["banned_groups"].remove(target)
                self._save_banlist()
                return True
            return False
        elif ban_type == "user":
            if target in self.banlist["banned_users"]:
                self.banlist["banned_users"].remove(target)
                self._save_banlist()
                return True
            return False
        return False

    def remove_blocked_word(self, word):
        """移除违禁词"""
        if word in self.banlist["blocked_words"]:
            self.banlist["blocked_words"].remove(word)
            self._save_banlist()
            return True
        return False

    def get_banlist(self):
        """获取ban列表"""
        return self.banlist

    def get_blocked_words(self):
        """获取违禁词列表"""
        return self.banlist["blocked_words"]

    def handle_ban_command(self, msg, admins, chat_model_instance):
        """处理ban命令"""
        return self._handle_ban_unban_command(msg, admins, chat_model_instance, is_ban=True)

    def handle_unban_command(self, msg, admins, chat_model_instance):
        """处理unban命令"""
        return self._handle_ban_unban_command(msg, admins, chat_model_instance, is_ban=False)

    def _handle_ban_unban_command(self, msg, admins, chat_model_instance, is_ban=True):
        """处理ban/unban命令的通用函数"""
        # 检查是否为管理员或超级管理员
        if hasattr(msg, 'user_id') and str(msg.user_id) not in admins and str(msg.user_id) != config.root:
            return "您没有权限执行此操作。", True

        # 检查是否被ban
        if self.is_banned(msg):
            return "您或您所在的群组已被禁止使用此功能。", True

        text = msg.raw_message.strip()
        parts = text.split()

        operation = "添加" if is_ban else "移除"
        command = "#ban_chat" if is_ban else "#ban_remove"
        reverse_status_word = "不在" if is_ban else "已"

        if len(parts) < 3:
            return f"指令格式错误。正确格式：{command} group <群号> 或 {command} user <QQ号> 或 {command} word <违禁词>", False
        else:
            action = parts[1]  # group || user || word
            target = parts[2]  # 群号 || QQ号 || 违禁词

            # 在添加 ban 时检查是否为超级管理员
            if is_ban and action in ["group", "user"] and target == config.root:
                return "禁止对超级管理员进行 ban 操作。", False

            if action == "group":
                if not target.isdigit():
                    return "群组ID必须为数字", False
                result = self.add_ban("group", target) if is_ban else self.remove_ban("group", target)
                if result:
                    return f"已将群组 {target} {operation}ban列表。", False
                else:
                    return f"群组 {target} {reverse_status_word}ban列表中。", False

            elif action == "user":
                if not target.isdigit():
                    return "用户ID必须为数字", False
                result = self.add_ban("user", target) if is_ban else self.remove_ban("user", target)
                if result:
                    return f"已将用户 {target} {operation}ban列表。", False
                else:
                    return f"用户 {target} {reverse_status_word}ban列表中。", False

            elif action == "word":
                result = self.add_blocked_word(target) if is_ban else self.remove_blocked_word(target)
                if result:
                    return f"已将违禁词 '{target}' {operation}列表。", False
                else:
                    return f"违禁词 '{target}' {reverse_status_word}列表中。", False

            else:
                return f"指令格式错误。正确格式：{command} group <群号> 或 {command} user <QQ号> 或 {command} word <违禁词>", False
