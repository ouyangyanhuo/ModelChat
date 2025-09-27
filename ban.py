# 优化后的 ban.py
from ncatbot.core import GroupMessage
from ncatbot.utils import config
from .utils import ConfigManager
import threading
from typing import Dict, List


class BanManager:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.config_manager = ConfigManager(plugin_dir)
        self.banlist_file = self.config_manager.get_data_path()
        self.banlist = self._load_banlist()
        # 添加线程锁以保证并发安全
        self.lock = threading.Lock()

    def _load_banlist(self) -> Dict[str, List[str]]:
        """加载ban列表"""
        try:
            # 通过ConfigManager加载数据
            data = self.config_manager.load_data()
            # 确保所有必要的键都存在
            required_keys = ["banned_groups", "banned_users", "blocked_words"]
            for key in required_keys:
                if key not in data:
                    data[key] = []

            return data
        except Exception as e:
            print(f"加载ban列表出错: {e}")
        return {"banned_groups": [], "banned_users": [], "blocked_words": []}

    def _save_banlist(self) -> bool:
        """保存ban列表"""
        try:
            # 通过ConfigManager保存数据
            with self.lock:
                self.config_manager.save_data(self.banlist)
            return True
        except Exception as e:
            print(f"保存ban列表出错: {e}")
            return False

    def is_banned(self, msg: GroupMessage) -> bool:
        """检查用户或群组是否被ban"""
        # 使用缓存避免频繁读取文件
        with self.lock:
            current_banlist = self.banlist

        # 检查用户是否被ban
        if hasattr(msg, 'user_id') and str(msg.user_id) in current_banlist["banned_users"]:
            return True

        # 检查群组是否被ban
        if hasattr(msg, 'group_id') and str(msg.group_id) in current_banlist["banned_groups"]:
            return True

        return False

    def check_blocked_words(self, text: str) -> bool:
        """检查文本是否包含违禁词"""
        # 使用缓存避免频繁读取文件
        with self.lock:
            blocked_words = self.banlist["blocked_words"]

        for block_word in blocked_words:
            if block_word in text:
                return True
        return False

    def add_ban(self, ban_type: str, target: str) -> bool:
        """添加ban项"""
        with self.lock:
            if ban_type == "group":
                if target not in self.banlist["banned_groups"]:
                    self.banlist["banned_groups"].append(target)
                    return self._save_banlist()
                return False
            elif ban_type == "user":
                if target not in self.banlist["banned_users"]:
                    self.banlist["banned_users"].append(target)
                    return self._save_banlist()
                return False
        return False

    def add_blocked_word(self, word: str) -> bool:
        """添加违禁词"""
        with self.lock:
            if word not in self.banlist["blocked_words"]:
                self.banlist["blocked_words"].append(word)
                return self._save_banlist()
        return False

    def remove_ban(self, ban_type: str, target: str) -> bool:
        """移除ban项"""
        with self.lock:
            if ban_type == "group":
                if target in self.banlist["banned_groups"]:
                    self.banlist["banned_groups"].remove(target)
                    return self._save_banlist()
                return False
            elif ban_type == "user":
                if target in self.banlist["banned_users"]:
                    self.banlist["banned_users"].remove(target)
                    return self._save_banlist()
                return False
        return False

    def remove_blocked_word(self, word: str) -> bool:
        """移除违禁词"""
        with self.lock:
            if word in self.banlist["blocked_words"]:
                self.banlist["blocked_words"].remove(word)
                return self._save_banlist()
        return False

    def get_banlist(self) -> Dict[str, List[str]]:
        """获取ban列表"""
        with self.lock:
            # 返回副本以防止外部修改
            return {
                "banned_groups": self.banlist["banned_groups"].copy(),
                "banned_users": self.banlist["banned_users"].copy(),
                "blocked_words": self.banlist["blocked_words"].copy()
            }

    def get_blocked_words(self) -> List[str]:
        """获取违禁词列表"""
        with self.lock:
            return self.banlist["blocked_words"].copy()

    def handle_ban_command(self, msg, admins) -> tuple:
        """处理ban命令"""
        return self._handle_ban_unban_command(msg, admins, is_ban=True)

    def handle_unban_command(self, msg, admins) -> tuple:
        """处理unban命令"""
        return self._handle_ban_unban_command(msg, admins, is_ban=False)

    def _handle_ban_unban_command(self, msg, admins, is_ban=True) -> tuple:
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
