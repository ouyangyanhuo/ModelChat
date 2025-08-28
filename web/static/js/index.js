// 获取当前用户名并显示
fetch('/api/current_user')
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            window.location.href = '/login';
        } else {
            document.getElementById('current-username').textContent = data.username;
        }
    })
    .catch(() => {
        window.location.href = '/login';
    });

// 检查是否为首次登录并显示提示
fetch('/check_first_login')
    .then(response => response.json())
    .then(data => {
        if (data.first_login) {
            document.getElementById('first-login-notification').classList.remove('hidden');
        }
    })
    .catch(error => {
        console.log('检查首次登录状态失败:', error);
    });

const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const typingIndicator = document.getElementById('typing-indicator');
const userIdElement = document.getElementById('user-id');
const changeUserButton = document.getElementById('change-user');
const clearHistoryButton = document.getElementById('clear-history');
const viewPromptButton = document.getElementById('view-prompt');
const themeToggleButton = document.getElementById('theme-toggle');
const promptModal = document.getElementById('prompt-modal');
const closePromptModal = document.getElementById('close-prompt-modal');
const promptContent = document.getElementById('prompt-content');
const changePasswordBtn = document.getElementById('change-password-btn');
const changePasswordFirstLogin = document.getElementById('change-password-first-login');
const passwordModal = document.getElementById('password-modal');
const closePasswordModal = document.getElementById('close-password-modal');
const cancelPasswordChange = document.getElementById('cancel-password-change');
const changePasswordForm = document.getElementById('change-password-form');

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

// 发送消息函数
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;
    
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
                user_id: parseInt(userIdElement.textContent),
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

// 添加消息到聊天窗口
function addMessageToChat(message, sender) {
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
}

// 更改用户ID
function changeUserId() {
    const newUserId = prompt('请输入新的用户ID:', userIdElement.textContent);
    if (newUserId && !isNaN(newUserId)) {
        userIdElement.textContent = newUserId;
    }
}

// 清除历史记录
async function clearHistory() {
    if (!confirm('确定要清除当前用户的历史记录吗？')) return;
    
    try {
        const response = await fetch(`/api/history/${userIdElement.textContent}/clear`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addMessageToChat('历史记录已清除', 'bot');
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

// 打开修改密码模态框
function openPasswordModal() {
    passwordModal.classList.remove('hidden');
}

// 关闭修改密码模态框
function closePasswordModalFunc() {
    passwordModal.classList.add('hidden');
    changePasswordForm.reset();
}

// 修改密码
async function changePassword(e) {
    e.preventDefault();
    
    const oldPassword = document.getElementById('old-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    if (newPassword !== confirmPassword) {
        alert('新密码和确认密码不一致');
        return;
    }
    
    try {
        const response = await fetch('/api/change_password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                old_password: oldPassword,
                new_password: newPassword
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('密码修改成功');
            // 隐藏首次登录提示（如果存在）
            document.getElementById('first-login-notification').classList.add('hidden');
            closePasswordModalFunc();
        } else {
            alert(`错误: ${data.error}`);
        }
    } catch (error) {
        alert(`网络错误: ${error.message}`);
    }
}

// 事件监听器
sendButton.addEventListener('click', sendMessage);

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

changeUserButton.addEventListener('click', changeUserId);
clearHistoryButton.addEventListener('click', clearHistory);
viewPromptButton.addEventListener('click', viewSystemPrompt);
themeToggleButton.addEventListener('click', toggleTheme);
closePromptModal.addEventListener('click', closePromptModalFunc);
changePasswordBtn.addEventListener('click', openPasswordModal);
changePasswordFirstLogin.addEventListener('click', openPasswordModal);
closePasswordModal.addEventListener('click', closePasswordModalFunc);
cancelPasswordChange.addEventListener('click', closePasswordModalFunc);
changePasswordForm.addEventListener('submit', changePassword);

// 点击模态框外部关闭
promptModal.addEventListener('click', (e) => {
    if (e.target === promptModal) {
        closePromptModalFunc();
    }
});

passwordModal.addEventListener('click', (e) => {
    if (e.target === passwordModal) {
        closePasswordModalFunc();
    }
});

// 页面加载完成后聚焦输入框
window.addEventListener('load', () => {
    messageInput.focus();
});
