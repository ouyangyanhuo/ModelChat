// 会话管理
let currentSessionId = null;
let sessions = {};
let currentUserId = 10000;

// 获取当前用户名并显示
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

const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const typingIndicator = document.getElementById('typing-indicator');
const clearHistoryButton = document.getElementById('clear-history');
const viewPromptButton = document.getElementById('view-prompt');
const themeToggleButton = document.getElementById('theme-toggle');
const promptModal = document.getElementById('prompt-modal');
const closePromptModal = document.getElementById('close-prompt-modal');
const promptContent = document.getElementById('prompt-content');

// 会话管理元素
const newSessionBtn = document.getElementById('new-session-btn');
const sessionList = document.getElementById('session-list');

let darkMode = localStorage.getItem('darkMode') === 'true';

// 应用主题
function applyTheme() {
    if (darkMode) {
        // 添加过渡效果类
        document.body.classList.add('bg-transition');
        setTimeout(() => {
            document.body.classList.add('dark-mode');
            themeToggleButton.innerHTML = '<i class="fas fa-sun"></i>';
            // 移除过渡效果类
            setTimeout(() => {
                document.body.classList.remove('bg-transition');
            }, 500);
        }, 10);
    } else {
        // 添加过渡效果类
        document.body.classList.add('bg-transition');
        setTimeout(() => {
            document.body.classList.remove('dark-mode');
            themeToggleButton.innerHTML = '<i class="fas fa-moon"></i>';
            // 移除过渡效果类
            setTimeout(() => {
                document.body.classList.remove('bg-transition');
            }, 500);
        }, 10);
    }
}

// 切换主题
function toggleTheme() {
    darkMode = !darkMode;
    localStorage.setItem('darkMode', darkMode);
    applyTheme();
}

// 应用保存的主题
applyTheme();

// 加载历史会话
function loadHistorySessions() {
    fetch('/api/sessions')
        .then(response => response.json())
        .then(data => {
            if (data.sessions) {
                sessions = data.sessions;
                
                // 如果没有会话，创建一个默认会话
                if (Object.keys(sessions).length === 0) {
                    createNewSession();
                } else {
                    // 选择第一个会话作为当前会话
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
            // 如果加载失败，创建一个默认会话
            if (Object.keys(sessions).length === 0) {
                createNewSession();
            }
        });
}

// 新建会话
newSessionBtn.addEventListener('click', function() {
    createNewSession();
});

// 创建新会话
function createNewSession() {
    // 生成新的用户ID（10000-10099范围内循环）
    let userIdFound = false;
    let newUserId = 10000;
    
    // 查找可用的用户ID
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
    
    // 如果所有ID都用完了，从10000开始循环（这种情况理论上不会发生，因为我们删除了会话）
    if (!userIdFound) {
        newUserId = 10000;
    }
    
    const sessionId = 'session_' + Date.now();
    sessions[sessionId] = {
        id: sessionId,
        name: '新会话',
        messages: [],
        userId: newUserId,
        createdAt: new Date().toISOString()
    };
    
    // 切换到新会话
    switchSession(sessionId);
    updateSessionList();
}

// 更新会话列表
function updateSessionList() {
    sessionList.innerHTML = '';
    
    // 按创建时间排序会话（最新的在上面）
    const sortedSessions = Object.values(sessions).sort((a, b) => {
        // 如果有createdAt，按createdAt排序，否则按ID排序
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
        if (session.messages.length > 0) {
            const lastMessage = session.messages[session.messages.length - 1];
            preview = lastMessage.content.length > 20 ? 
                lastMessage.content.substring(0, 20) + '...' : 
                lastMessage.content;
        }
        
        sessionItem.innerHTML = `
            <div class="flex-1 min-w-0">
                <div class="session-title">${session.name}</div>
                <div class="session-preview">${preview}</div>
            </div>
            <div class="session-actions">
                <button class="delete-session" data-session-id="${session.id}">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        
        // 点击切换会话
        sessionItem.addEventListener('click', function(e) {
            if (!e.target.classList.contains('delete-session') && 
                !e.target.parentElement.classList.contains('delete-session')) {
                switchSession(session.id);
            }
        });
        
        // 删除会话
        const deleteBtn = sessionItem.querySelector('.delete-session');
        deleteBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            deleteSession(session.id);
        });
        
        sessionList.appendChild(sessionItem);
    });
}

// 切换会话
function switchSession(sessionId) {
    if (sessions[sessionId]) {
        currentSessionId = sessionId;
        currentUserId = sessions[sessionId].userId;
        renderMessages();
        updateSessionList();
    }
}

// 删除会话
function deleteSession(sessionId) {
    // 检查是否只剩一个会话
    const sessionCount = Object.keys(sessions).length;
    if (sessionCount <= 1) {
        // 如果只剩一个会话，删除后创建一个新的默认会话
        if (confirm('这是最后一个会话，删除后将创建一个新的默认会话。确定要删除吗？')) {
            // 获取要删除的用户ID
            const userId = sessions[sessionId].userId;
            
            // 调用API删除会话
            fetch(`/api/session/${userId}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // 从本地sessions对象中删除会话
                    delete sessions[sessionId];
                    
                    // 创建一个新的默认会话
                    createNewSession();
                } else {
                    alert('删除会话失败: ' + (data.error || '未知错误'));
                }
            })
            .catch(error => {
                alert('删除会话时发生网络错误: ' + error.message);
            });
        }
    } else {
        // 如果有多个会话，直接删除
        if (confirm('确定要删除这个会话吗？')) {
            // 获取要删除的用户ID
            const userId = sessions[sessionId].userId;
            
            // 调用API删除会话
            fetch(`/api/session/${userId}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // 从本地sessions对象中删除会话
                    delete sessions[sessionId];
                    
                    // 如果删除的是当前会话，切换到第一个会话
                    if (sessionId === currentSessionId) {
                        const firstSessionId = Object.keys(sessions)[0];
                        switchSession(firstSessionId);
                    }
                    
                    // 更新会话列表
                    updateSessionList();
                } else {
                    alert('删除会话失败: ' + (data.error || '未知错误'));
                }
            })
            .catch(error => {
                alert('删除会话时发生网络错误: ' + error.message);
            });
        }
    }
}

// 渲染消息
function renderMessages() {
    chatContainer.innerHTML = '';
    
    if (!currentSessionId) return;
    
    const currentSession = sessions[currentSessionId];
    if (currentSession && currentSession.messages.length > 0) {
        currentSession.messages.forEach(message => {
            addMessageToChat(message.content, message.sender, false);
        });
    } else {
        // 显示欢迎消息
        const welcomeMessage = document.createElement('div');
        welcomeMessage.className = 'chat-bubble bot-bubble';
        welcomeMessage.innerHTML = `
            <div class="flex items-center">
                <i class="fas fa-robot mr-2"></i>
                <span>欢迎使用ModelChat！请输入您的消息开始对话。</span>
            </div>
        `;
        chatContainer.appendChild(welcomeMessage);
    }
    
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// 生成会话名称
function generateSessionName(firstMessage) {
    // 简单的会话名称生成逻辑 - 取消息的前10个字符作为会话名
    // 在实际应用中，可以调用AI来生成更智能的会话名称
    if (firstMessage.length > 10) {
        return firstMessage.substring(0, 10) + '...';
    }
    return firstMessage;
}

// 添加消息到聊天窗口
function addMessageToChat(message, sender, saveToSession = true) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-bubble ${sender}-bubble`;
    
    if (sender === 'bot') {
        messageDiv.innerHTML = `
            <div class="flex items-start">
                <i class="fas fa-robot mr-2 mt-1"></i>
                <div>${message}</div>
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="flex items-start justify-end">
                <div>${message}</div>
                <i class="fas fa-user ml-2 mt-1"></i>
            </div>
        `;
    }
    
    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    // 保存消息到当前会话
    if (saveToSession && currentSessionId) {
        if (!sessions[currentSessionId].messages) {
            sessions[currentSessionId].messages = [];
        }
        
        sessions[currentSessionId].messages.push({
            content: message,
            sender: sender,
            timestamp: new Date().toISOString()
        });
        
        // 如果这是会话的第一条用户消息，则用它来生成会话名称
        if (sessions[currentSessionId].messages.length === 1 && sender === 'user') {
            sessions[currentSessionId].name = generateSessionName(message);
            updateSessionList();
        }
    }
}

// 发送消息函数
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;
    
    // 确保有一个当前会话
    if (!currentSessionId) {
        createNewSession();
    }
    
    // 显示用户消息
    addMessageToChat(message, 'user');
    messageInput.value = '';
    
    // 显示正在输入指示器
    typingIndicator.style.display = 'block';
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    try {
        // 调用API
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: sessions[currentSessionId].userId,
                message: message
            })
        });
        
        const data = await response.json();
        
        // 隐藏正在输入指示器
        typingIndicator.style.display = 'none';
        
        if (response.ok) {
            addMessageToChat(data.response, 'bot');
        } else if (response.status === 401) {
            window.location.href = '/login';
        } else {
            addMessageToChat(`错误: ${data.error}`, 'bot');
        }
    } catch (error) {
        typingIndicator.style.display = 'none';
        addMessageToChat(`网络错误: ${error.message}`, 'bot');
    }
    
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// 清除历史记录
async function clearHistory() {
    if (!confirm('确定要清除当前会话的历史记录吗？')) return;
    
    if (!currentSessionId) return;
    
    try {
        const response = await fetch(`/api/history/${sessions[currentSessionId].userId}/clear`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // 清空当前会话的消息
            sessions[currentSessionId].messages = [];
            renderMessages();
            addMessageToChat('会话历史已清除', 'bot');
        } else {
            addMessageToChat(`错误: ${data.error}`, 'bot');
        }
    } catch (error) {
        addMessageToChat(`网络错误: ${error.message}`, 'bot');
    }
}

// 查看系统提示词
async function viewSystemPrompt() {
    try {
        const response = await fetch('/api/system_prompt');
        const data = await response.json();
        
        if (response.ok) {
            promptContent.textContent = data.prompt;
            promptModal.classList.remove('hidden');
        } else {
            addMessageToChat(`错误: ${data.error}`, 'bot');
        }
    } catch (error) {
        addMessageToChat(`网络错误: ${error.message}`, 'bot');
    }
}

// 关闭提示词模态框
function closePromptModalFunc() {
    promptModal.classList.add('hidden');
}

// 事件监听器
sendButton.addEventListener('click', sendMessage);

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

clearHistoryButton.addEventListener('click', clearHistory);
viewPromptButton.addEventListener('click', viewSystemPrompt);
themeToggleButton.addEventListener('click', toggleTheme);
closePromptModal.addEventListener('click', closePromptModalFunc);

// 点击模态框外部关闭
promptModal.addEventListener('click', (e) => {
    if (e.target === promptModal) {
        closePromptModalFunc();
    }
});

// 页面加载完成后聚焦输入框并加载历史会话
window.addEventListener('load', () => {
    messageInput.focus();
    loadHistorySessions();
});
