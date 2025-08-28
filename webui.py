from flask import Flask, render_template, request, jsonify
from .api import ModelChatAPI
import os
import threading
import webbrowser
import asyncio

class ModelChatWebUI:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.api = ModelChatAPI(plugin_dir)
        self.app = Flask(__name__, 
                         template_folder=os.path.join(plugin_dir, 'templates'),
                         static_folder=os.path.join(plugin_dir, 'static'))
        self._setup_routes()
        
    def _setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template('index.html')
            
        @self.app.route('/api/chat', methods=['POST'])
        def chat():
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
            try:
                prompt = self.api.get_system_prompt()
                return jsonify({'prompt': prompt})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
                
        @self.app.route('/api/system_prompt', methods=['POST'])
        def set_system_prompt():
            data = request.json
            prompt = data.get('prompt', '')
            try:
                self.api.set_system_prompt(prompt)
                return jsonify({'success': True})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
                
        @self.app.route('/api/history/<int:user_id>', methods=['GET'])
        def get_history(user_id):
            try:
                history = self.api.get_user_history(user_id)
                return jsonify({'history': history})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
                
        @self.app.route('/api/history/<int:user_id>/clear', methods=['POST'])
        def clear_history(user_id):
            try:
                result = self.api.clear_user_history(user_id)
                return jsonify({'result': result})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

    def run(self, host='127.0.0.1', port=5000, debug=False, open_browser=True):
        if open_browser:
            threading.Timer(1.25, lambda: webbrowser.open(f'http://{host}:{port}')).start()
            
        self.app.run(host=host, port=port, debug=debug)
