# -*- coding: utf-8 -*-
"""数据库初始化脚本 - 创建表并插入默认数据"""
import models

if __name__ == '__main__':
    models.init_db()
