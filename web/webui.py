from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from plugins.ModelChat.api import ModelChatAPI
from ncatbot.utils import config as bot_config
import os
import threading
import webbrowser
import asyncio
import hashlib
import secrets
import json

class ModelChatWebUI:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.api = ModelChatAPI(plugin_dir)
        self.app = Flask(__name__, 
                         template_folder=os.path.join(plugin_dir, 'web', 'templates'),
                         static_folder=os.path.join(plugin_dir, 'web', 'static'))
        
        # 生成用于会话的密钥
        self.app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
        
        # 密码文件路径
        self.password_file = os.path.join(plugin_dir, 'web', 'password.json')
        self.default_password = "123456"
        self._ensure_password_file()
        
        self._setup_routes()
        
    def _ensure_password_file(self):
        """确保密码文件存在"""
        if not os.path.exists(self.password_file):
            # 创建默认密码文件
            default_data = {
                "password": ""
            }
            with open(self.password_file, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
        else:
            # 检查文件内容
            try:
                with open(self.password_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if not data or "password" not in data:
                    # 文件为空或格式不正确，重新创建
                    default_data = {
                        "password": ""
                    }
                    with open(self.password_file, 'w', encoding='utf-8') as f:
                        json.dump(default_data, f, ensure_ascii=False, indent=2)
            except (json.JSONDecodeError, FileNotFoundError):
                # 文件损坏或无法读取，重新创建
                default_data = {
                    "password": ""
                }
                with open(self.password_file, 'w', encoding='utf-8') as f:
                    json.dump(default_data, f, ensure_ascii=False, indent=2)
                
    def _load_passwords(self):
        """加载密码文件"""
        try:
            with open(self.password_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"password": ""}
            
    def _save_passwords(self, data):
        """保存密码文件"""
        with open(self.password_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    def _hash_password(self, password):
        """哈希密码"""
        return hashlib.sha256(password.encode()).hexdigest()
        
    def _get_admin_user_id(self):
        """获取超级管理员用户ID"""
        return bot_config.root

    def _setup_routes(self):
        @self.app.route('/check_first_login')
        def check_first_login():
            # 检查是否为首次登录
            passwords_data = self._load_passwords()
            is_first_login = not passwords_data.get("password", "")
            return jsonify({'first_login': is_first_login})

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                # 处理JSON请求数据或表单数据
                if request.is_json:
                    data = request.get_json()
                    username = data.get('username')
                    password = data.get('password')
                else:
                    username = request.form.get('username')
                    password = request.form.get('password')
                
                # 获取超级管理员ID
                admin_id = self._get_admin_user_id()
                
                # 检查用户名是否正确
                if username != admin_id:
                    if request.is_json:
                        return jsonify({'error': '用户名或密码错误'}), 401
                    else:
                        return render_template('login.html', error='用户名或密码错误')
                
                # 加载密码数据
                passwords_data = self._load_passwords()
                stored_password_hash = passwords_data.get("password", "")
                
                # 如果没有设置密码，则使用默认密码123456
                if not stored_password_hash:
                    if password == self.default_password:
                        # 使用默认密码登录成功，要求设置新密码
                        session['temp_authenticated'] = True
                        session['temp_username'] = username
                        if request.is_json:
                            return jsonify({'redirect': url_for('set_password')})
                        else:
                            return redirect(url_for('set_password'))
                else:
                    # 验证密码
                    if self._hash_password(password) == stored_password_hash:
                        # 登录成功
                        session['authenticated'] = True
                        session['username'] = username
                        token = secrets.token_hex(16)
                        session['token'] = token
                        
                        # 设置cookie
                        resp = make_response(jsonify({'redirect': url_for('index')}))
                        resp.set_cookie('token', token, httponly=True)
                        return resp
                
                if request.is_json:
                    return jsonify({'error': '用户名或密码错误'}), 401
                else:
                    return render_template('login.html', error='用户名或密码错误')
            
            return render_template('login.html')
            
        @self.app.route('/set_password', methods=['GET', 'POST'])
        def set_password():
            # 检查是否有临时认证
            if not session.get('temp_authenticated'):
                return redirect(url_for('login'))
                
            if request.method == 'POST':
                # 处理JSON请求数据或表单数据
                if request.is_json:
                    data = request.get_json()
                    new_password = data.get('new_password')
                    confirm_password = data.get('confirm_password')
                else:
                    new_password = request.form.get('new_password')
                    confirm_password = request.form.get('confirm_password')
                
                if not new_password or not confirm_password:
                    if request.is_json:
                        return jsonify({'error': '密码不能为空'}), 400
                    else:
                        return render_template('set_password.html', error='密码不能为空')
                    
                if new_password != confirm_password:
                    if request.is_json:
                        return jsonify({'error': '两次输入的密码不一致'}), 400
                    else:
                        return render_template('set_password.html', error='两次输入的密码不一致')
                
                if len(new_password) < 6:
                    if request.is_json:
                        return jsonify({'error': '密码长度至少为6位'}), 400
                    else:
                        return render_template('set_password.html', error='密码长度至少为6位')
                
                # 保存新密码
                passwords_data = self._load_passwords()
                passwords_data['password'] = self._hash_password(new_password)
                self._save_passwords(passwords_data)
                
                # 清除临时会话
                session.pop('temp_authenticated', None)
                session.pop('temp_username', None)
                
                # 设置正式会话
                username = session.get('temp_username', self._get_admin_user_id())
                session['authenticated'] = True
                session['username'] = username
                token = secrets.token_hex(16)
                session['token'] = token
                
                # 设置cookie
                resp = make_response(jsonify({'redirect': url_for('index')}))
                resp.set_cookie('token', token, httponly=True)
                return resp
            
            return render_template('set_password.html')
            
        @self.app.route('/logout')
        def logout():
            session.pop('authenticated', None)
            session.pop('username', None)
            session.pop('token', None)
            session.pop('temp_authenticated', None)
            session.pop('temp_username', None)
            resp = make_response(redirect(url_for('login')))
            resp.set_cookie('token', '', expires=0)
            return resp
        
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
                
        @self.app.route('/api/session/<int:user_id>', methods=['DELETE'])
        def delete_session(user_id):
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
            
            try:
                # 删除指定用户的历史记录
                result = self.api.delete_user_history(user_id)
                if result:
                    return jsonify({'success': True})
                else:
                    return jsonify({'error': '删除失败'}), 500
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/current_user')
        def current_user():
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
            
            return jsonify({'username': session.get('username', 'unknown')})
            
        @self.app.route('/api/sessions', methods=['GET'])
        def get_sessions():
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
            
            try:
                # 只获取 10000 - 10099 范围内的用户ID
                allowed_user_ids = list(range(10000, 10100))
                sessions = self.api.get_history_sessions(allowed_user_ids)
                return jsonify({'sessions': sessions})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/config', methods=['GET'])
        def get_config():
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
            
            try:
                config = self.api.get_config()
                return jsonify({'config': config})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/config', methods=['POST'])
        def save_config():
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
            
            try:
                data = request.json
                config_data = data.get('config', {})
                
                result = self.api.save_config(config_data)
                if result:
                    return jsonify({'success': True})
                else:
                    return jsonify({'error': '保存配置失败'}), 500
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/config', methods=['PATCH'])
        def update_config():
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
            
            try:
                data = request.json
                updates = data.get('updates', {})
                
                result = self.api.update_config(updates)
                if result:
                    # 更新配置后重新加载所有配置
                    self.api.reload_all_configs()
                    return jsonify({'success': True})
                else:
                    return jsonify({'error': '更新配置失败'}), 500
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/change_password', methods=['POST'])
        def change_password():
            if not session.get('authenticated'):
                return jsonify({'error': '未授权访问'}), 401
                
            data = request.json
            old_password = data.get('old_password', '')
            new_password = data.get('new_password', '')
            
            if not old_password or not new_password:
                return jsonify({'error': '密码不能为空'}), 400
                
            # 验证旧密码
            passwords = self._load_passwords()
            stored_password_hash = passwords.get("password", "")
            if self._hash_password(old_password) != stored_password_hash:
                return jsonify({'error': '旧密码错误'}), 400
                    
            # 更新密码
            passwords["password"] = self._hash_password(new_password)
            self._save_passwords(passwords)
            return jsonify({'success': True})

    def run(self, host='127.0.0.1', port=5000, debug=False, open_browser=True):
        # 设置安全相关的HTTP头
        @self.app.after_request
        def after_request(response):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            return response
        
        if open_browser:
            threading.Timer(1.25, lambda: webbrowser.open(f'http://{host}:{port}')).start()
            
        self.app.run(host=host, port=port, debug=debug)
