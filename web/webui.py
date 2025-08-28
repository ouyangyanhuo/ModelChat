from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from .api import ModelChatAPI
import os
import threading
import webbrowser
import asyncio
import hashlib
import secrets

class ModelChatWebUI:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.api = ModelChatAPI(plugin_dir)
        self.app = Flask(__name__, 
                         template_folder=os.path.join(plugin_dir, 'templates'),
                         static_folder=os.path.join(plugin_dir, 'static'))
        # 生成随机密钥用于会话
        self.app.secret_key = secrets.token_hex(16)
        self._setup_routes()
        
        # 从配置中读取认证信息
        self.username = os.environ.get('MODELCHAT_WEBUI_USERNAME', 'admin')
        self.password_hash = os.environ.get('MODELCHAT_WEBUI_PASSWORD_HASH', 
                                           hashlib.sha256(b'admin123').hexdigest())  # 默认密码: admin123
        
    def _setup_routes(self):
        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                username = request.form.get('username')
                password = request.form.get('password')
                
                # 验证用户名和密码
                if (username == self.username and 
                    hashlib.sha256(password.encode()).hexdigest() == self.password_hash):
                    session['authenticated'] = True
                    session['username'] = username
                    return redirect(url_for('index'))
                else:
                    return render_template('login.html', error='用户名或密码错误')
            
            return render_template('login.html')
            
        @self.app.route('/logout')
        def logout():
            session.pop('authenticated', None)
            session.pop('username', None)
            return redirect(url_for('login'))
        
        @self.app.route('/')
        def index():
            if not session.get('authenticated'):
                return redirect(url_for('login'))
            return render_template('index.html')
            
        @self.app.route('/api/chat', methods=['POST'])
        def chat():
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
                
            data = request.json
            user_id = data.get('user_id', 0)
            message = data.get('message', '')
            group_id = data.get('group_id')
            
            try:
                # 使用asyncio.run来运行异步函数
                response = asyncio.run(self.api.generate_response(user_id, message, group_id))
                return jsonify({'response': response})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
                
        @self.app.route('/api/system_prompt', methods=['GET'])
        def get_system_prompt():
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
                
            try:
                prompt = self.api.get_system_prompt()
                return jsonify({'prompt': prompt})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
                
        @self.app.route('/api/system_prompt', methods=['POST'])
        def set_system_prompt():
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
                
            data = request.json
            prompt = data.get('prompt', '')
            try:
                self.api.set_system_prompt(prompt)
                return jsonify({'success': True})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
                
        @self.app.route('/api/history/<int:user_id>', methods=['GET'])
        def get_history(user_id):
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
                
            try:
                history = self.api.get_user_history(user_id)
                return jsonify({'history': history})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
                
        @self.app.route('/api/history/<int:user_id>/clear', methods=['POST'])
        def clear_history(user_id):
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
                
            try:
                result = self.api.clear_user_history(user_id)
                return jsonify({'result': result})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/current_user')
        def current_user():
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
            
            return jsonify({'username': session.get('username', 'unknown')})

    def run(self, host='127.0.0.1', port=5000, debug=False, open_browser=True):
        if open_browser:
            threading.Timer(1.25, lambda: webbrowser.open(f'http://{host}:{port}')).start()
            
        self.app.run(host=host, port=port, debug=debug)
