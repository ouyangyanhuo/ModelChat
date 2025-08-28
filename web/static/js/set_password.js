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

// 处理设置密码表单提交
document.getElementById('set-password-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const newPassword = document.getElementById('new_password').value;
    const confirmPassword = document.getElementById('confirm_password').value;
    const setPasswordButton = document.querySelector('.auth-button');
    const setPasswordText = document.getElementById('set-password-text');
    
    // 显示加载状态
    setPasswordText.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 设置中...';
    setPasswordButton.disabled = true;
    
    try {
        // 发送设置密码请求
        const response = await fetch('/set_password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                new_password: newPassword,
                confirm_password: confirmPassword
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // 设置密码成功，重定向到主页面
            window.location.href = data.redirect;
        } else {
            showError(data.error);
            setPasswordText.textContent = '设置密码并登录';
            setPasswordButton.disabled = false;
        }
    } catch (error) {
        showError('网络错误，请稍后重试');
        setPasswordText.textContent = '设置密码并登录';
        setPasswordButton.disabled = false;
    }
});
