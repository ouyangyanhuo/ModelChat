# 指令配置文件
# 仅超级管理员可执行的指令
SUPER_ADMIN_ONLY_COMMANDS = ["Add Admin", "Remove Admin", "System Prompt", "Add Clear Word", "Remove Clear Word","List Admins","List Clear Words"]
# 普通用户指令
USER_COMMANDS = [
    {
        "name": "Start Chat",
        "prefix": "#start_chat",
        "handler": "start_chat",
        "description": "开始持续对话模式",
        "examples": ["#start_chat"]
    },
    {
        "name": "End Chat",
        "prefix": "#stop_chat",
        "handler": "stop_chat",
        "description": "结束持续对话模式",
        "examples": ["#stop_chat"]
    },
    {
        "name": "ModelChat",
        "prefix": "#chat",
        "handler": "chat",
        "description": "单次聊天功能",
        "examples": ["#chat <message>", "#chat <photo>", "#chat <message>+<photo>"]
    },
    {
        "name": "Clear History",
        "prefix": "#clear chat_history",
        "handler": "chat_history",
        "description": "清除聊天记忆",
        "examples": ["#clear chat_history"]
    },
    {
        "name": "Chat Menu",
        "prefix": "聊天菜单",
        "handler": "chat_menu",
        "description": "显示聊天插件的使用菜单",
        "examples": ["聊天菜单"]
    },
]

# 管理员指令
ADMIN_COMMANDS = [
    {
        "name": "Ban Manager",
        "prefix": "#ban_chat",
        "handler": "ban_manager",
        "description": "添加违禁词 或 禁止群组/人使用该插件",
        "examples": ["#ban_chat word <message>", "#ban_chat group <groupID>", "#ban_chat user <userID>"]
    },
    {
        "name": "Unban Manager",
        "prefix": "#ban_remove",
        "handler": "unban_manager",
        "description": "移除违禁词 或 解除群组/人的禁用",
        "examples": ["#ban_remove word <message>", "#ban_remove group <groupID>", "#ban_remove user <userID>"]
    },
    {
        "name": "System Prompt",
        "prefix": "#system_prompt",
        "handler": "system_prompt_handler",
        "description": "修改系统提示词",
        "examples": ["#system_prompt <提示词>"]
    },
    {
        "name": "Add Clear Word",
        "prefix": "#add_clear_word",
        "handler": "add_clear_word",
        "description": "添加输出过滤词",
        "examples": ["#add_clear_word <过滤词>"]
    },
    {
        "name": "Remove Clear Word",
        "prefix": "#remove_clear_word",
        "handler": "remove_clear_word",
        "description": "删除输出过滤词",
        "examples": ["#remove_clear_word <过滤词>"]
    },
    {
        "name": "List Clear Words",
        "prefix": "#list_clear_words",
        "handler": "list_clear_words",
        "description": "查看输出过滤词列表",
        "examples": ["#list_clear_words"]
    },
    {
        "name": "Add Admin",
        "prefix": "#add_admin",
        "handler": "add_admin",
        "description": "添加管理员",
        "examples": ["#add_admin <QQ号>"]
    },
    {
        "name": "Remove Admin",
        "prefix": "#remove_admin",
        "handler": "remove_admin",
        "description": "删除管理员",
        "examples": ["#remove_admin <QQ号>"]
    },
    {
        "name": "List Admins",
        "prefix": "#list_admins",
        "handler": "list_admins",
        "description": "查看管理员列表",
        "examples": ["#list_admins"]
    }
]
