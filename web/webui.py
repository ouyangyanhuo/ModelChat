from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from plugins.ModelChat.api import ModelChatAPI
from ncatbot.utils import config as bot_config
from functools import wraps
import os, threading, webbrowser, asyncio, hashlib, secrets, json

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
            self._create_default_password_file()
        else:
            # 检查文件内容
            try:
                with open(self.password_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if not data or "password" not in data:
                    # 文件为空或格式不正确，重新创建
                    self._create_default_password_file()
            except (json.JSONDecodeError, FileNotFoundError):
                # 文件损坏或无法读取，重新创建
                self._create_default_password_file()
    
    def _create_default_password_file(self):
        """创建默认密码文件"""
        default_data = {"password": ""}
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

    def _require_auth(self, f):
        """认证装饰器"""
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not session.get('authenticated'):
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': '未授权访问'}), 401
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapper

    def _handle_form_or_json(self, request):
        """处理表单或JSON请求数据"""
        if request.is_json:
            return request.get_json()
        else:
            # 将表单数据转换为字典
            return request.form.to_dict()

    def _json_response(self, data, status_code=200):
        """统一JSON响应格式"""
        response = jsonify(data)
        response.status_code = status_code
        return response

    def _redirect_response(self, endpoint):
        """统一重定向响应格式"""
        if request.is_json:
            return self._json_response({'redirect': url_for(endpoint)})
        else:
            return redirect(url_for(endpoint))

    def _error_response(self, message, status_code=400):
        """统一错误响应格式"""
        if request.is_json or request.path.startswith('/api/'):
            return self._json_response({'error': message}, status_code)
        else:
            # 对于登录页面的错误，渲染模板并传递错误信息
            if request.endpoint == 'login':
                return render_template('login.html', error=message)
            elif request.endpoint == 'set_password':
                return render_template('set_password.html', error=message)
            else:
                return self._json_response({'error': message}, status_code)

    def _setup_routes(self):
        @self.app.route('/check_first_login')
        def check_first_login():
            # 检查是否为首次登录
            passwords_data = self._load_passwords()
            is_first_login = not passwords_data.get("password", "")
            return self._json_response({'first_login': is_first_login})

        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                # 处理JSON请求数据或表单数据
                data = self._handle_form_or_json(request)
                username = data.get('username')
                password = data.get('password')
                
                # 获取超级管理员ID
                admin_id = self._get_admin_user_id()
                
                # 检查用户名是否正确
                if username != admin_id:
                    return self._error_response('用户名或密码错误', 401)
                
                # 加载密码数据
                passwords_data = self._load_passwords()
                stored_password_hash = passwords_data.get("password", "")
                
                # 如果没有设置密码，则使用默认密码123456
                if not stored_password_hash:
                    if password == self.default_password:
                        # 使用默认密码登录成功，要求设置新密码
                        session['temp_authenticated'] = True
                        session['temp_username'] = username
                        return self._redirect_response('set_password')
                else:
                    # 验证密码
                    if self._hash_password(password) == stored_password_hash:
                        # 登录成功
                        session['authenticated'] = True
                        session['username'] = username
                        token = secrets.token_hex(16)
                        session['token'] = token
                        
                        # 设置cookie
                        resp = self._redirect_response('index')
                        if not request.is_json:
                            resp = make_response(resp)
                        resp.set_cookie('token', token, httponly=True, secure=request.is_secure)
                        return resp
                
                return self._error_response('用户名或密码错误', 401)
            
            return render_template('login.html')
            
        @self.app.route('/set_password', methods=['GET', 'POST'])
        def set_password():
            # 检查是否有临时认证
            if not session.get('temp_authenticated'):
                return self._redirect_response('login')
                
            if request.method == 'POST':
                # 处理JSON请求数据或表单数据
                data = self._handle_form_or_json(request)
                new_password = data.get('new_password')
                confirm_password = data.get('confirm_password')
                
                if not new_password or not confirm_password:
                    return self._error_response('密码不能为空', 400)
                    
                if new_password != confirm_password:
                    return self._error_response('两次输入的密码不一致', 400)
                
                if len(new_password) < 6:
                    return self._error_response('密码长度至少为6位', 400)
                
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
                resp = self._redirect_response('index')
                if not request.is_json:
                    resp = make_response(resp)
                resp.set_cookie('token', token, httponly=True, secure=request.is_secure)
                return resp
            
            return render_template('set_password.html')
            
        @self.app.route('/logout')
        def logout():
            session.clear()
            resp = make_response(redirect(url_for('login')))
            resp.set_cookie('token', '', expires=0)
            return resp
        
        @self.app.route('/')
        def index():
            if not session.get('authenticated'):
                return self._redirect_response('login')
            return render_template('index.html')
            
        @self.app.route('/api/chat', methods=['POST'])
        @self._require_auth
        def chat():
            data = request.json
            user_id = data.get('user_id', 0)
            message = data.get('message', '')
            group_id = data.get('group_id')
            
            try:
                response = asyncio.run(self.api.generate_response(user_id, message, group_id))
                return self._json_response({'response': response})
            except Exception as e:
                return self._json_response({'error': str(e)}, 500)
                
        @self.app.route('/api/system_prompt', methods=['GET'])
        @self._require_auth
        def get_system_prompt():
            try:
                prompt = self.api.get_system_prompt()
                return self._json_response({'prompt': prompt})
            except Exception as e:
                return self._json_response({'error': str(e)}, 500)
                
        @self.app.route('/api/system_prompt', methods=['POST'])
        @self._require_auth
        def set_system_prompt():
            data = request.json
            prompt = data.get('prompt', '')
            try:
                self.api.set_system_prompt(prompt)
                return self._json_response({'success': True})
            except Exception as e:
                return self._json_response({'error': str(e)}, 500)
                
        @self.app.route('/api/history/<int:user_id>', methods=['GET'])
        @self._require_auth
        def get_history(user_id):
            try:
                history = self.api.get_user_history(user_id)
                return self._json_response({'history': history})
            except Exception as e:
                return self._json_response({'error': str(e)}, 500)
                
        @self.app.route('/api/history/<int:user_id>/clear', methods=['POST'])
        @self._require_auth
        def clear_history(user_id):
            try:
                result = self.api.clear_user_history(user_id)
                return self._json_response({'result': result})
            except Exception as e:
                return self._json_response({'error': str(e)}, 500)
                
        @self.app.route('/api/session/<int:user_id>', methods=['DELETE'])
        @self._require_auth
        def delete_session(user_id):
            try:
                # 删除指定用户的历史记录
                result = self.api.delete_user_history(user_id)
                if result:
                    return self._json_response({'success': True})
                else:
                    return self._json_response({'error': '删除失败'}, 500)
            except Exception as e:
                return self._json_response({'error': str(e)}, 500)

        @self.app.route('/api/current_user')
        @self._require_auth
        def current_user():
            return self._json_response({'username': session.get('username', 'unknown')})
            
        @self.app.route('/api/sessions', methods=['GET'])
        @self._require_auth
        def get_sessions():
            try:
                # 只获取 10000 - 10099 范围内的用户ID
                allowed_user_ids = list(range(10000, 10100))
                sessions = self.api.get_history_sessions(allowed_user_ids)
                return self._json_response({'sessions': sessions})
            except Exception as e:
                return self._json_response({'error': str(e)}, 500)

        @self.app.route('/api/config', methods=['GET'])
        @self._require_auth
        def get_config():
            try:
                config = self.api.get_config()
                return self._json_response({'config': config})
            except Exception as e:
                return self._json_response({'error': str(e)}, 500)

        @self.app.route('/api/config', methods=['POST'])
        @self._require_auth
        def save_config():
            try:
                data = request.json
                config_data = data.get('config', {})
                
                result = self.api.save_config(config_data)
                if result:
                    return self._json_response({'success': True})
                else:
                    return self._json_response({'error': '保存配置失败'}, 500)
            except Exception as e:
                return self._json_response({'error': str(e)}, 500)

        @self.app.route('/api/config', methods=['PATCH'])
        @self._require_auth
        def update_config():
            try:
                data = request.json
                updates = data.get('updates', {})
                
                result = self.api.update_config(updates)
                if result:
                    # 更新配置后重新加载所有配置
                    self.api.reload_all_configs()
                    return self._json_response({'success': True})
                else:
                    return self._json_response({'error': '更新配置失败'}, 500)
            except Exception as e:
                return self._json_response({'error': str(e)}, 500)

        @self.app.route('/api/change_password', methods=['POST'])
        @self._require_auth
        def change_password():
            data = request.json
            old_password = data.get('old_password', '')
            new_password = data.get('new_password', '')
            
            if not old_password or not new_password:
                return self._json_response({'error': '密码不能为空'}, 400)
                
            # 验证旧密码
            passwords = self._load_passwords()
            stored_password_hash = passwords.get("password", "")
            if self._hash_password(old_password) != stored_password_hash:
                return self._json_response({'error': '旧密码错误'}, 400)
                    
            # 更新密码
            passwords["password"] = self._hash_password(new_password)
            self._save_passwords(passwords)
            return self._json_response({'success': True})

    def run(self, host='127.0.0.1', port=5000, debug=False, open_browser=True):
        # 设置安全相关的HTTP头
        @self.app.after_request
        def after_request(response):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            return response
        
        if open_browser and not debug:
            threading.Timer(1.25, lambda: webbrowser.open(f'http://{host}:{port}')).start()
            
        self.app.run(host=host, port=port, debug=debug)
