// 显示错误消息
function showError(message) {
    const errorContainer = document.getElementById('error-container');
    errorContainer.innerHTML = `
        <div class="error-message bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            <div class="flex items-center">
                <i class="fas fa-exclamation-circle mr-2"></i>
                <span>${message}</span>
            </div>
        </div>
    `;
}

// 检查是否为首次登录
async function checkFirstLogin() {
    try {
        const response = await fetch('/check_first_login');
        if (response.ok) {
            const data = await response.json();
            if (data.first_login) {
                document.getElementById('first-login-hint').classList.remove('hidden');
            }
        }
    } catch (error) {
        console.log('检查首次登录状态失败:', error);
    }
}

// 处理登录表单提交
document.getElementById('login-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const loginButton = document.querySelector('.auth-button');
    const loginText = document.getElementById('login-text');
    
    // 显示加载状态
    loginText.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 登录中...';
    loginButton.disabled = true;
    
    try {
        // 发送登录请求
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // 登录成功，重定向
            window.location.href = data.redirect;
        } else {
            showError(data.error);
            loginText.textContent = '登录';
            loginButton.disabled = false;
        }
    } catch (error) {
        showError('网络错误，请稍后重试');
        loginText.textContent = '登录';
        loginButton.disabled = false;
    }
});

// 页面加载时检查是否为首次登录
document.addEventListener('DOMContentLoaded', function() {
    checkFirstLogin();
    
    // 检查本地存储的主题设置
    if (localStorage.getItem('darkMode') === 'true') {
        document.body.classList.add('dark-mode');
    }
});
