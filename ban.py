import json,os
from ncatbot.core import GroupMessage

class BanManager:
    def __init__(self, plugin_dir):
        self.banlist_file = os.path.join(plugin_dir, 'banlist.json')
        self.banlist = self._load_banlist()

    def _load_banlist(self):
        """加载ban列表"""
        try:
            if os.path.exists(self.banlist_file):
                with open(self.banlist_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
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
            with open(self.banlist_file, 'w', encoding='utf-8') as f:
                json.dump(self.banlist, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存ban列表出错: {e}")

    def is_banned(self, msg: GroupMessage):
        """检查用户或群组是否被ban"""
        # 检查用户是否被ban
        if hasattr(msg, 'user_id') and str(msg.user_id) in self.banlist["banned_users"]:
            return True

        # 检查群组是否被ban
        if hasattr(msg, 'group_id') and str(msg.group_id) in self.banlist["banned_groups"]:
            return True

        return False

    def check_blocked_words(self, text):
        """检查文本是否包含违禁词"""
        for block_word in self.banlist["blocked_words"]:
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

    def get_banlist(self):
        """获取ban列表"""
        return self.banlist

    def get_blocked_words(self):
        """获取违禁词列表"""
        return self.banlist["blocked_words"]
