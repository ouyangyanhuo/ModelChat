// ==========================
// index.lib.js (仅供开发使用)
// ==========================

// 当前会话ID
let currentSessionId = null;
// 会话集合（内存）
let sessions = {};
// 默认用户ID起始值（用于本地生成 session user id）
let currentUserId = 10000;

// ==========================
// 登录状态检查：若未登录跳转 /login
// ==========================
fetch('/api/current_user')
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            window.location.href = '/login';
        }
    })
    .catch(() => {
        window.location.href = '/login';
    });

// ==========================
// DOM 元素引用（页面可能没有某些元素，使用时请做好检查）
// ==========================
const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const typingIndicator = document.getElementById('typing-indicator');
const themeToggleButton = document.getElementById('theme-toggle');
const promptModal = document.getElementById('prompt-modal');
const closePromptModal = document.getElementById('close-prompt-modal');
const promptContent = document.getElementById('prompt-content');
const settingsBtn = document.getElementById('settings-btn');
const settingsMenu = document.getElementById('settings-menu');
const viewPromptBtn = document.getElementById('view-prompt-btn');
const changePasswordBtn = document.getElementById('change-password-btn');
const passwordModal = document.getElementById('password-modal');
const closePasswordModal = document.getElementById('close-password-modal');
const cancelPasswordChange = document.getElementById('cancel-password-change');
const changePasswordForm = document.getElementById('change-password-form');
const newSessionBtn = document.getElementById('new-session-btn');
const sessionList = document.getElementById('session-list');

// ==========================
// 主题（暗黑模式）管理
// ==========================
let darkMode = localStorage.getItem('darkMode') === 'true';

function applyTheme() {
    if (darkMode) {
        document.body.classList.add('dark-mode');
        if (themeToggleButton) themeToggleButton.innerHTML = '<i class="fas fa-sun"></i>';
    } else {
        document.body.classList.remove('dark-mode');
        if (themeToggleButton) themeToggleButton.innerHTML = '<i class="fas fa-moon"></i>';
    }
}

function toggleTheme() {
    darkMode = !darkMode;
    localStorage.setItem('darkMode', darkMode);
    applyTheme();
}

// 点击设置按钮切换菜单显示
if (settingsBtn) {
    settingsBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (settingsMenu) settingsMenu.classList.toggle('hidden');
    });
}

// 点击页面任意处关闭设置菜单（若打开且点击不在菜单/按钮区域）
document.addEventListener('click', function (e) {
    if (settingsMenu && !settingsMenu.classList.contains('hidden') &&
        settingsBtn && !settingsBtn.contains(e.target) &&
        settingsMenu && !settingsMenu.contains(e.target)) {
        settingsMenu.classList.add('hidden');
    }
});

// ==========================
// 原生JS实现的轻量Markdown渲染
// 支持：#标题、**加粗**、*斜体*、`行内代码`、```代码块```、[链接](url)、换行
// ==========================
function renderMarkdownToHtml(text) {
    if (!text) return '';

    // 先做 HTML 转义，避免注入风险
    let html = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // 代码块（多行） ```lang\n code \n``` -> <pre><code>...</code></pre>
    html = html.replace(/```([\s\S]*?)```/g, function(_, code) {
        return '<pre><code>' + code.trim() + '</code></pre>';
    });

    // 标题 (支持 #, ##, ###)
    html = html.replace(/^### (.*)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.*)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.*)$/gm, '<h1>$1</h1>');

    // 粗体 **text**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // 斜体 *text*
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // 行内代码 `code`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // 链接 [text](url)
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

    // 换行：把剩余的换行转为 <br>
    html = html.replace(/\r?\n/g, '<br>');

    return html;
}


// ==========================
// 加载历史会话（从后端 /api/sessions）
// ==========================
function loadHistorySessions() {
    fetch('/api/sessions')
        .then(response => response.json())
        .then(data => {
            if (data.sessions) {
                sessions = data.sessions;
                if (Object.keys(sessions).length === 0) {
                    createNewSession();
                } else {
                    const firstSessionId = Object.keys(sessions)[0];
                    currentSessionId = firstSessionId;
                    currentUserId = sessions[firstSessionId].userId;
                }
                updateSessionList();
                renderMessages();
            }
        })
        .catch(error => {
            console.error('加载历史会话失败:', error);
            if (Object.keys(sessions).length === 0) {
                createNewSession();
            }
        });
}

if (newSessionBtn) {
    newSessionBtn.addEventListener('click', function () {
        createNewSession();
    });
}

// ==========================
// 创建新会话：在 sessions 中添加并切换到该会话
// ==========================
function createNewSession() {
    let userIdFound = false;
    let newUserId = 10000;
    for (let i = 10000; i <= 10099; i++) {
        let userIdUsed = false;
        for (let sessionId in sessions) {
            if (sessions[sessionId].userId === i) {
                userIdUsed = true;
                break;
            }
        }
        if (!userIdUsed) {
            newUserId = i;
            userIdFound = true;
            break;
        }
    }
    if (!userIdFound) newUserId = 10000;

    const sessionId = 'session_' + Date.now();
    sessions[sessionId] = {
        id: sessionId,
        name: '新会话',
        messages: [],
        userId: newUserId,
        createdAt: new Date().toISOString()
    };
    switchSession(sessionId);
    updateSessionList();
}

// ==========================
// 更新会话列表 DOM
// ==========================
function updateSessionList() {
    if (!sessionList) return;
    sessionList.innerHTML = '';

    const sortedSessions = Object.values(sessions).sort((a, b) => {
        if (a.createdAt && b.createdAt) {
            return new Date(b.createdAt) - new Date(a.createdAt);
        }
        return b.id.localeCompare(a.id);
    });

    sortedSessions.forEach(session => {
        const sessionItem = document.createElement('div');
        sessionItem.className = `session-item ${session.id === currentSessionId ? 'active' : ''}`;
        sessionItem.dataset.sessionId = session.id;

        let preview = '新会话';
        if (session.messages && session.messages.length > 0) {
            const lastMessage = session.messages[session.messages.length - 1];
            preview = lastMessage.content.length > 20 ? lastMessage.content.substring(0, 20) + '...' : lastMessage.content;
        }

        sessionItem.innerHTML = `
            <div class="flex-1 min-w-0">
                <div class="session-title">${escapeHtml(session.name || '无名会话')}</div>
                <div class="session-preview">${escapeHtml(preview)}</div>
            </div>
            <div class="session-actions">
                <button class="delete-session" data-session-id="${session.id}">
                    <i class="fas fa-trash"></i>
                </button>
            </div>`;

        // 点击切换会话（排除点击删除按钮）
        sessionItem.addEventListener('click', function (e) {
            if (!e.target.classList.contains('delete-session') && !e.target.parentElement.classList.contains('delete-session')) {
                switchSession(session.id);
            }
        });

        // 删除按钮处理
        const deleteBtn = sessionItem.querySelector('.delete-session');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                deleteSession(session.id);
            });
        }

        sessionList.appendChild(sessionItem);
    });
}

// 辅助：简单转义（用于插入会话名称、预览等非 Markdown 内容）
function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// ==========================
// 切换会话（改变 currentSessionId 并渲染）
// ==========================
function switchSession(sessionId) {
    if (sessions[sessionId]) {
        currentSessionId = sessionId;
        currentUserId = sessions[sessionId].userId;
        renderMessages();
        updateSessionList();
    }
}

// ==========================
// 删除会话（调用后端 API 并更新本地 sessions）
// ==========================
function deleteSession(sessionId) {
    const sessionCount = Object.keys(sessions).length;
    if (sessionCount <= 1) {
        if (!confirm('这是最后一个会话，删除后将创建一个新的默认会话。确定要删除吗？')) return;
    } else {
        if (!confirm('确定要删除这个会话吗？')) return;
    }

    const userId = sessions[sessionId] ? sessions[sessionId].userId : null;
    if (userId == null) {
        // 若没有 userId，直接在本地删除
        delete sessions[sessionId];
        if (Object.keys(sessions).length === 0) createNewSession();
        updateSessionList();
        return;
    }

    fetch(`/api/session/${userId}`, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                delete sessions[sessionId];
                if (Object.keys(sessions).length === 0) {
                    createNewSession();
                } else if (sessionId === currentSessionId) {
                    const firstSessionId = Object.keys(sessions)[0];
                    switchSession(firstSessionId);
                }
                updateSessionList();
            } else {
                alert('删除会话失败: ' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            alert('删除会话时发生网络错误: ' + error.message);
        });
}

// ==========================
// 渲染当前会话的消息（会调用 addMessageToChat）
// ==========================
function renderMessages() {
    if (!chatContainer) return;
    chatContainer.innerHTML = '';
    if (!currentSessionId) return;

    const currentSession = sessions[currentSessionId];
    if (currentSession && currentSession.messages && currentSession.messages.length > 0) {
        currentSession.messages.forEach(message => {
            addMessageToChat(message.content, message.sender, false);
        });
    } else {
        // 没有历史消息，显示欢迎语
        const welcomeMessage = document.createElement('div');
        welcomeMessage.className = 'chat-bubble bot-bubble';
        welcomeMessage.innerHTML = `
            <div class="flex items-center">
                <i class="fas fa-robot mr-2"></i>
                <span>欢迎使用ModelChat！请输入您的消息开始对话。</span>
            </div>`;
        chatContainer.appendChild(welcomeMessage);
    }
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// ==========================
// 生成会话名称（用第一条消息的前 10 字作为会话名）
// ==========================
function generateSessionName(firstMessage) {
    if (!firstMessage) return '新会话';
    if (firstMessage.length > 10) {
        return firstMessage.substring(0, 10) + '...';
    }
    return firstMessage;
}

// ==========================
// 添加消息到聊天窗口（支持 Markdown 渲染）
// 参数：message - 字符串；sender - 'user' 或 'bot'；saveToSession - 是否保存到本地 sessions
// ==========================
function addMessageToChat(message, sender, saveToSession = true) {
    if (!chatContainer) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-bubble ${sender}-bubble`;

    // 使用渲染器将消息转换为 HTML（并已尽量保证安全）
    const renderedMessage = renderMarkdownToHtml(message);

    if (sender === 'bot') {
        messageDiv.innerHTML = `
            <div class="flex items-start">
                <i class="fas fa-robot mr-2 mt-1"></i>
                <div class="markdown-body" style="max-width: 100%;">${renderedMessage}</div>
            </div>`;
    } else {
        messageDiv.innerHTML = `
            <div class="flex items-start justify-end">
                <div class="markdown-body" style="max-width: 100%;">${renderedMessage}</div>
                <i class="fas fa-user ml-2 mt-1"></i>
            </div>`;
    }

    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // 保存到本地会话数据
    if (saveToSession && currentSessionId) {
        if (!sessions[currentSessionId].messages) sessions[currentSessionId].messages = [];
        sessions[currentSessionId].messages.push({
            content: message,
            sender: sender,
            timestamp: new Date().toISOString()
        });

        // 如果是用户发的第一条消息，更新会话名称
        if (sessions[currentSessionId].messages.length === 1 && sender === 'user') {
            sessions[currentSessionId].name = generateSessionName(message);
            updateSessionList();
        }
    }
}

// ==========================
// 发送消息到后端 /api/chat
// ==========================
async function sendMessage() {
    if (!messageInput) return;
    const message = messageInput.value.trim();
    if (!message) return;

    if (!currentSessionId) createNewSession();

    // 先在本地界面显示用户消息
    addMessageToChat(message, 'user');
    messageInput.value = '';
    if (typingIndicator) typingIndicator.style.display = 'block';
    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: sessions[currentSessionId].userId,
                message: message
            })
        });

        const data = await response.json();
        if (typingIndicator) typingIndicator.style.display = 'none';

        if (response.ok) {
            // 后端返回的 data.response 可能包含 Markdown
            addMessageToChat(data.response, 'bot');
        } else if (response.status === 401) {
            window.location.href = '/login';
        } else {
            addMessageToChat(`错误: ${data.error || '未知错误'}`, 'bot');
        }
    } catch (error) {
        if (typingIndicator) typingIndicator.style.display = 'none';
        addMessageToChat(`网络错误: ${error.message}`, 'bot');
    }

    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
}

// ==========================
// 清除当前会话历史（调用后端并清空本地）
// ==========================
async function clearHistory() {
    if (!confirm('确定要清除当前会话的历史记录吗？')) return;
    if (!currentSessionId) return;

    try {
        const response = await fetch(`/api/history/${sessions[currentSessionId].userId}/clear`, { method: 'POST' });
        const data = await response.json();
        if (response.ok) {
            sessions[currentSessionId].messages = [];
            renderMessages();
            addMessageToChat('会话历史已清除', 'bot');
        } else {
            addMessageToChat(`错误: ${data.error || '清除失败'}`, 'bot');
        }
    } catch (error) {
        addMessageToChat(`网络错误: ${error.message}`, 'bot');
    }
}

// ==========================
// 系统提示词（查看 / 编辑）
// ==========================
const systemPromptText = document.getElementById('system-prompt-text');
const savePromptButton = document.getElementById('save-prompt-button');
const cancelPromptChange = document.getElementById('cancel-prompt-change');

async function viewSystemPrompt() {
    try {
        const response = await fetch('/api/system_prompt');
        const data = await response.json();
        if (response.ok) {
            if (systemPromptText) systemPromptText.value = data.prompt || '';
            if (promptModal) promptModal.classList.remove('hidden');
        } else {
            alert(`加载系统提示词失败: ${data.error || '未知错误'}`);
        }
    } catch (error) {
        alert(`网络错误: ${error.message}`);
    }
}

function closePromptModalFunc() {
    if (promptModal) promptModal.classList.add('hidden');
}

async function saveSystemPrompt() {
    if (!systemPromptText) return;
    try {
        const response = await fetch('/api/system_prompt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: systemPromptText.value })
        });
        const data = await response.json();
        if (response.ok) {
            alert('系统提示词已保存');
            if (promptModal) promptModal.classList.add('hidden');
        } else {
            alert(`保存失败: ${data.error || '未知错误'}`);
        }
    } catch (error) {
        alert(`网络错误: ${error.message}`);
    }
}

// ==========================
// 修改密码逻辑
// ==========================
async function changePassword(e) {
    if (e && typeof e.preventDefault === 'function') e.preventDefault();
    const oldPasswordEl = document.getElementById('old-password');
    const newPasswordEl = document.getElementById('new-password');
    const confirmPasswordEl = document.getElementById('confirm-password');

    const oldPassword = oldPasswordEl ? oldPasswordEl.value : '';
    const newPassword = newPasswordEl ? newPasswordEl.value : '';
    const confirmPassword = confirmPasswordEl ? confirmPasswordEl.value : '';

    if (newPassword !== confirmPassword) {
        alert('新密码和确认密码不一致');
        return;
    }

    try {
        const response = await fetch('/api/change_password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
        });
        const data = await response.json();
        if (response.ok) {
            alert('密码修改成功');
            if (passwordModal) passwordModal.classList.add('hidden');
            if (changePasswordForm) changePasswordForm.reset();
        } else {
            alert(`错误: ${data.error || '修改失败'}`);
        }
    } catch (error) {
        alert(`网络错误: ${error.message}`);
    }
}

// ==========================
// 更多设置（Modal 显示与隐藏）
// ==========================
const moreSettingsBtn = document.getElementById('more-settings-btn');
const moreSettingsModal = document.getElementById('more-settings-modal');
const closeMoreSettingsModal = document.getElementById('close-more-settings-modal');
const settingsForm = document.getElementById('settings-form');
const cancelSettingsBtn = document.getElementById('cancel-settings');

if (moreSettingsBtn) {
    moreSettingsBtn.addEventListener('click', function () {
        if (settingsMenu) settingsMenu.classList.add('hidden');
        loadConfigAndShowSettings();
    });
}
if (closeMoreSettingsModal) {
    closeMoreSettingsModal.addEventListener('click', function () {
        if (moreSettingsModal) moreSettingsModal.classList.add('hidden');
    });
}
if (cancelSettingsBtn) {
    cancelSettingsBtn.addEventListener('click', function () {
        if (moreSettingsModal) moreSettingsModal.classList.add('hidden');
    });
}
if (moreSettingsModal) {
    moreSettingsModal.addEventListener('click', function (e) {
        if (e.target === moreSettingsModal) moreSettingsModal.classList.add('hidden');
    });
}

// ==========================
// 加载配置并显示在更多设置中
// ==========================
async function loadConfigAndShowSettings() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        if (response.ok) {
            const config = data.config || {};

            // 以下逐项回填表单（若元素存在则赋值）
            const setIfExists = (id, value) => {
                const el = document.getElementById(id);
                if (!el) return;
                if (el.type === 'checkbox') {
                    el.checked = !!value;
                } else {
                    el.value = value !== undefined && value !== null ? value : '';
                }
            };

            setIfExists('api_key', config.api_key || '');
            setIfExists('base_url', config.base_url || '');
            setIfExists('model', config.model || '');
            setIfExists('vision_api_key', config.vision_api_key || '');
            setIfExists('vision_base_url', config.vision_base_url || '');
            setIfExists('vision_model', config.vision_model || '');
            setIfExists('memory_length', config.memory_length || '');
            setIfExists('model_temperature', config.model_temperature || '');
            setIfExists('enable_vision', config.enable_vision || false);
            setIfExists('enable_mcp', config.enable_mcp || false);
            setIfExists('enable_export', config.enable_export || false);
            setIfExists('enable_webui', config.enable_webui || false);
            setIfExists('enable_continuous_session', config.enable_continuous_session !== undefined ? config.enable_continuous_session : true);
            setIfExists('webui_host', config.webui_host || '127.0.0.1');
            setIfExists('webui_port', config.webui_port || 5000);
            setIfExists('webui_open_browser', config.webui_open_browser || false);

            if (moreSettingsModal) moreSettingsModal.classList.remove('hidden');
        } else {
            alert('加载配置失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        alert('加载配置时发生网络错误: ' + error.message);
    }
}

// ==========================
// settings 表单提交（保存配置）
// - 获取当前配置（用于判断是否需要重启）
// - 提交 PATCH /api/config { updates: {...} }
// ==========================
if (settingsForm) {
    settingsForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        // 先尝试读取当前后端配置以便比较（容错）
        let currentConfig = {};
        try {
            const resp = await fetch('/api/config');
            const d = await resp.json();
            if (resp.ok) currentConfig = d.config || {};
        } catch (err) {
            console.warn('获取当前配置时出错，继续以表单值为准', err);
        }

        const updates = {};
        const fields = ['api_key', 'base_url', 'model', 'vision_api_key', 'vision_base_url', 'vision_model', 'memory_length', 'model_temperature', 'enable_vision', 'enable_mcp', 'enable_export', 'enable_webui', 'webui_host', 'webui_port', 'webui_open_browser', 'enable_continuous_session'];

        fields.forEach(field => {
            const el = document.getElementById(field);
            if (!el) return;
            if (el.type === 'checkbox') {
                updates[field] = el.checked;
            } else if (el.type === 'number') {
                const val = el.value;
                updates[field] = val !== '' ? (field.includes('temperature') ? parseFloat(val) : parseInt(val)) : '';
            } else {
                updates[field] = el.value;
            }
        });

        // 这些字段改变后需要重启服务才能生效
        const requiresRestart = ['enable_webui', 'webui_host', 'webui_port', 'webui_open_browser', 'enable_continuous_session'];
        let needRestart = false;
        for (const field of requiresRestart) {
            if (updates[field] !== undefined && updates[field] !== currentConfig[field]) {
                needRestart = true;
                break;
            }
        }

        try {
            const response = await fetch('/api/config', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ updates: updates })
            });
            const data = await response.json();
            if (response.ok) {
                if (needRestart) {
                    alert('设置已保存，但检测到您修改了需要重启的配置（WebUI/持续会话等）。请手动重启服务以使其生效。');
                } else {
                    alert('设置已保存并生效');
                }
                if (moreSettingsModal) moreSettingsModal.classList.add('hidden');
                if (!needRestart) location.reload();
            } else {
                alert('保存设置失败: ' + (data.error || '未知错误'));
            }
        } catch (error) {
            alert('保存设置时发生网络错误: ' + error.message);
        }
    });
}

// ==========================
// 页面事件绑定（按钮、输入回车等）
// ==========================
if (sendButton) sendButton.addEventListener('click', sendMessage);
if (messageInput) {
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            // 回车发送（Shift+Enter 保留换行）
            e.preventDefault();
            sendMessage();
        }
    });
}
if (viewPromptBtn) viewPromptBtn.addEventListener('click', viewSystemPrompt);
if (changePasswordBtn) changePasswordBtn.addEventListener('click', function () { if (passwordModal) passwordModal.classList.remove('hidden'); });
if (closePromptModal) closePromptModal.addEventListener('click', closePromptModalFunc);
if (closePasswordModal) closePasswordModal.addEventListener('click', function () { if (passwordModal) passwordModal.classList.add('hidden'); });
if (cancelPasswordChange) cancelPasswordChange.addEventListener('click', function () { if (passwordModal) passwordModal.classList.add('hidden'); });
if (changePasswordForm) changePasswordForm.addEventListener('submit', changePassword);
if (savePromptButton) savePromptButton.addEventListener('click', saveSystemPrompt);
if (cancelPromptChange) cancelPromptChange.addEventListener('click', closePromptModalFunc);
if (promptModal) {
    promptModal.addEventListener('click', (e) => { if (e.target === promptModal) closePromptModalFunc(); });
}
if (passwordModal) {
    passwordModal.addEventListener('click', (e) => { if (e.target === passwordModal) passwordModal.classList.add('hidden'); });
}
if (themeToggleButton) themeToggleButton.addEventListener('click', toggleTheme);

// ==========================
// 初始化：窗口加载时应用主题、聚焦输入框并加载历史会话
// ==========================
window.addEventListener('load', () => {
    applyTheme();
    if (messageInput) messageInput.focus();
    loadHistorySessions();
});
