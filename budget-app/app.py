# -*- coding: utf-8 -*-
"""
预算与支出管理系统 - Flask 应用入口
启动方式: python app.py  或  双击 start.bat
访问地址: http://localhost:5000
"""

import os
import sys

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, send_from_directory
from werkzeug.middleware.shared_data import SharedDataMiddleware

import models
from routes import api

# 创建 Flask 应用
app = Flask(__name__, static_folder='static', static_url_path='/static')

# 配置
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR

# 确保必要目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'), exist_ok=True)

# 注册 API 蓝图
app.register_blueprint(api, url_prefix='/api')


@app.route('/')
def index():
    """提供前端页面"""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def static_files(path):
    """静态文件服务"""
    return send_from_directory(app.static_folder, path)


if __name__ == '__main__':
    # 初始化数据库
    print("Initializing database...")
    models.init_db()

    print("\n" + "=" * 50)
    print("  Budget & Expense Management System")
    print("  URL: http://localhost:5000")
    print("  Press Ctrl+C to stop")
    print("=" * 50 + "\n")

    # 启动服务器（允许局域网访问）
    app.run(host='0.0.0.0', port=5000, debug=True)
