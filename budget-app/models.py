# -*- coding: utf-8 -*-
"""
数据库模型层 - SQLite 数据库的建表和 CRUD 操作
"""

import sqlite3
import os
from datetime import datetime

# 数据库文件路径
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'budget.db')


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    """初始化数据库，创建所有表"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            icon TEXT DEFAULT '📌',
            color TEXT DEFAULT '#4A90D9',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS project_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            icon TEXT DEFAULT '📂',
            color TEXT DEFAULT '#6C5CE7',
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            group_id INTEGER,
            icon TEXT DEFAULT '📁',
            color TEXT DEFAULT '#4A90D9',
            sort_order INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (group_id) REFERENCES project_groups(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            contact TEXT DEFAULT '',
            note TEXT DEFAULT '',
            contract_signed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            category_id INTEGER,
            amount REAL NOT NULL,
            supplier TEXT DEFAULT '',
            expense_detail TEXT DEFAULT '',
            note TEXT DEFAULT '',
            attachment_path TEXT,
            attachment_name TEXT,
            submitter TEXT DEFAULT '',
            payer TEXT DEFAULT '',
            payment_status TEXT DEFAULT 'pending',
            payment_date TEXT,
            payment_note TEXT DEFAULT '',
            budget_month TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_budgets_status ON budgets(payment_status);
        CREATE INDEX IF NOT EXISTS idx_budgets_month ON budgets(budget_month);
        CREATE INDEX IF NOT EXISTS idx_budgets_project ON budgets(project_id);
        CREATE INDEX IF NOT EXISTS idx_budgets_category ON budgets(category_id);
    ''')

    # 插入默认成员（如果表为空）
    cursor.execute("SELECT COUNT(*) FROM members")
    if cursor.fetchone()[0] == 0:
        cursor.executescript('''
            INSERT INTO members (name, role) VALUES ('张三', 'member');
            INSERT INTO members (name, role) VALUES ('李四', 'member');
            INSERT INTO members (name, role) VALUES ('王五', 'payer');
            INSERT INTO members (name, role) VALUES ('赵六', 'payer');
        ''')

    # 插入默认分类
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        cursor.executescript('''
            INSERT INTO categories (name, icon, color) VALUES ('人力成本', '👥', '#E17055');
            INSERT INTO categories (name, icon, color) VALUES ('物料采购', '📦', '#00B894');
            INSERT INTO categories (name, icon, color) VALUES ('差旅费', '✈️', '#0984E3');
            INSERT INTO categories (name, icon, color) VALUES ('办公费用', '🖨️', '#6C5CE7');
            INSERT INTO categories (name, icon, color) VALUES ('营销推广', '📢', '#F39C12');
            INSERT INTO categories (name, icon, color) VALUES ('外包服务', '🤝', '#00CEC9');
            INSERT INTO categories (name, icon, color) VALUES ('研发支出', '🔬', '#FD79A8');
            INSERT INTO categories (name, icon, color) VALUES ('其他支出', '📌', '#636E72');
        ''')

    # 插入默认项目分组
    cursor.execute("SELECT COUNT(*) FROM project_groups")
    if cursor.fetchone()[0] == 0:
        cursor.executescript('''
            INSERT INTO project_groups (name, icon, color) VALUES ('客户项目', '🤝', '#4A90D9');
            INSERT INTO project_groups (name, icon, color) VALUES ('内部管理', '🏢', '#6C5CE7');
        ''')

    # 插入默认项目（关联分组）
    cursor.execute("SELECT COUNT(*) FROM projects")
    if cursor.fetchone()[0] == 0:
        cursor.executescript('''
            INSERT INTO projects (name, description, group_id, icon, color) VALUES ('Q3产品研发', '第三季度核心产品研发项目', 1, '🚀', '#4A90D9');
            INSERT INTO projects (name, description, group_id, icon, color) VALUES ('市场推广活动', '年度市场推广与品牌建设', 1, '📢', '#E17055');
            INSERT INTO projects (name, description, group_id, icon, color) VALUES ('办公环境改造', '新办公室装修与设备采购', 2, '🏗️', '#00B894');
        ''')

    # 兼容旧数据库：projects 表如果没有 group_id 列则添加
    try:
        cursor.execute("ALTER TABLE projects ADD COLUMN group_id INTEGER REFERENCES project_groups(id) ON DELETE SET NULL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE projects ADD COLUMN sort_order INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE project_groups ADD COLUMN sort_order INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE suppliers ADD COLUMN contract_signed INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
    print("[OK] Database initialized successfully")


# ==================== 成员 CRUD ====================

def get_all_members():
    conn = get_db()
    rows = conn.execute("SELECT * FROM members WHERE active = 1 ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_member(name, role='member'):
    conn = get_db()
    cursor = conn.execute("INSERT INTO members (name, role) VALUES (?, ?)", (name, role))
    conn.commit()
    mid = cursor.lastrowid
    conn.close()
    return mid


def update_member(mid, name=None, role=None):
    conn = get_db()
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if role is not None:
        fields.append("role = ?")
        values.append(role)
    if fields:
        values.append(mid)
        conn.execute(f"UPDATE members SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def delete_member(mid):
    """软删除成员"""
    conn = get_db()
    conn.execute("UPDATE members SET active = 0 WHERE id = ?", (mid,))
    conn.commit()
    conn.close()


# ==================== 分类 CRUD ====================

def get_all_categories():
    conn = get_db()
    rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_category(name, icon='📌', color='#4A90D9'):
    conn = get_db()
    cursor = conn.execute("INSERT INTO categories (name, icon, color) VALUES (?, ?, ?)", (name, icon, color))
    conn.commit()
    cid = cursor.lastrowid
    conn.close()
    return cid


def update_category(cid, name=None, icon=None, color=None):
    conn = get_db()
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if icon is not None:
        fields.append("icon = ?")
        values.append(icon)
    if color is not None:
        fields.append("color = ?")
        values.append(color)
    if fields:
        values.append(cid)
        conn.execute(f"UPDATE categories SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def delete_category(cid):
    conn = get_db()
    conn.execute("UPDATE budgets SET category_id = NULL WHERE category_id = ?", (cid,))
    conn.execute("DELETE FROM categories WHERE id = ?", (cid,))
    conn.commit()
    conn.close()


# ==================== 项目分组 CRUD ====================

def get_all_project_groups():
    conn = get_db()
    rows = conn.execute("SELECT * FROM project_groups ORDER BY sort_order, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_project_group(name, icon='📂', color='#6C5CE7'):
    conn = get_db()
    cursor = conn.execute("INSERT INTO project_groups (name, icon, color) VALUES (?, ?, ?)",
                          (name, icon, color))
    conn.commit()
    gid = cursor.lastrowid
    conn.close()
    return gid


def update_project_group(gid, name=None, icon=None, color=None):
    conn = get_db()
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if icon is not None:
        fields.append("icon = ?")
        values.append(icon)
    if color is not None:
        fields.append("color = ?")
        values.append(color)
    if fields:
        values.append(gid)
        conn.execute(f"UPDATE project_groups SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def delete_project_group(gid):
    conn = get_db()
    conn.execute("UPDATE projects SET group_id = NULL WHERE group_id = ?", (gid,))
    conn.execute("DELETE FROM project_groups WHERE id = ?", (gid,))
    conn.commit()
    conn.close()


def reorder_project_groups(items):
    """批量更新分组排序: items = [{id, sort_order}, ...]"""
    import time
    for attempt in range(5):
        try:
            conn = get_db()
            conn.execute("BEGIN IMMEDIATE")
            for it in items:
                conn.execute("UPDATE project_groups SET sort_order = ? WHERE id = ?",
                             (it['sort_order'], it['id']))
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError:
            try: conn.close()
            except: pass
            if attempt < 4:
                time.sleep(0.1)
            else:
                raise


# ==================== 项目 CRUD ====================

def get_all_projects():
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY sort_order, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reorder_projects(items):
    """批量更新项目排序: items = [{id, group_id, sort_order}, ...]"""
    import time
    for attempt in range(5):
        try:
            conn = get_db()
            conn.execute("BEGIN IMMEDIATE")
            for it in items:
                conn.execute("UPDATE projects SET group_id = ?, sort_order = ? WHERE id = ?",
                             (it.get('group_id'), it.get('sort_order', 0), it['id']))
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError:
            try: conn.close()
            except: pass
            if attempt < 4:
                time.sleep(0.1)
            else:
                raise


def add_project(name, description='', icon='📁', color='#4A90D9', group_id=None):
    conn = get_db()
    cursor = conn.execute("INSERT INTO projects (name, description, icon, color, group_id) VALUES (?, ?, ?, ?, ?)",
                          (name, description, icon, color, group_id))
    conn.commit()
    pid = cursor.lastrowid
    conn.close()
    return pid


def update_project(pid, name=None, description=None, icon=None, color=None, status=None, group_id=None, **kwargs):
    conn = get_db()
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if description is not None:
        fields.append("description = ?")
        values.append(description)
    if icon is not None:
        fields.append("icon = ?")
        values.append(icon)
    if color is not None:
        fields.append("color = ?")
        values.append(color)
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    # Use a sentinel to distinguish "not provided" from "set to null"
    if '_set_group_id' in kwargs:
        fields.append("group_id = ?")
        values.append(kwargs['_set_group_id'])
    if fields:
        values.append(pid)
        conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()



def delete_project(pid):
    conn = get_db()
    conn.execute("UPDATE budgets SET project_id = NULL WHERE project_id = ?", (pid,))
    conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
    conn.commit()
    conn.close()


# ==================== 供应商 CRUD ====================

def get_all_suppliers():
    conn = get_db()
    rows = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_supplier(name, contact='', note='', contract_signed=0):
    conn = get_db()
    cursor = conn.execute("INSERT INTO suppliers (name, contact, note, contract_signed) VALUES (?, ?, ?, ?)",
                          (name, contact, note, contract_signed))
    conn.commit()
    sid = cursor.lastrowid
    conn.close()
    return sid


def update_supplier(sid, name=None, contact=None, note=None, contract_signed=None):
    conn = get_db()
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if contact is not None:
        fields.append("contact = ?")
        values.append(contact)
    if note is not None:
        fields.append("note = ?")
        values.append(note)
    if contract_signed is not None:
        fields.append("contract_signed = ?")
        values.append(contract_signed)
    if fields:
        values.append(sid)
        conn.execute(f"UPDATE suppliers SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def delete_supplier(sid):
    conn = get_db()
    conn.execute("DELETE FROM suppliers WHERE id = ?", (sid,))
    conn.commit()
    conn.close()


# ==================== 预算 CRUD ====================

def get_all_budgets(status=None, month=None, project_id=None, category_id=None, keyword=None):
    """获取预算列表，支持多种筛选条件"""
    conn = get_db()
    query = "SELECT b.*, p.name as project_name, p.icon as project_icon, p.color as project_color, c.name as category_name, c.icon as category_icon, c.color as category_color FROM budgets b LEFT JOIN projects p ON b.project_id = p.id LEFT JOIN categories c ON b.category_id = c.id WHERE 1=1"
    params = []

    if status and status != 'all':
        query += " AND b.payment_status = ?"
        params.append(status)
    if month and month != 'all':
        query += " AND b.budget_month = ?"
        params.append(month)
    if project_id and project_id != 'all':
        query += " AND b.project_id = ?"
        params.append(int(project_id))
    if category_id and category_id != 'all':
        query += " AND b.category_id = ?"
        params.append(int(category_id))
    if keyword:
        query += " AND (b.supplier LIKE ? OR b.note LIKE ? OR b.expense_detail LIKE ? OR b.submitter LIKE ? OR b.payer LIKE ?)"
        kw = f"%{keyword}%"
        params.extend([kw, kw, kw, kw, kw])

    query += " ORDER BY b.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_budget_by_id(bid):
    conn = get_db()
    row = conn.execute(
        "SELECT b.*, p.name as project_name, p.icon as project_icon, p.color as project_color, c.name as category_name, c.icon as category_icon, c.color as category_color FROM budgets b LEFT JOIN projects p ON b.project_id = p.id LEFT JOIN categories c ON b.category_id = c.id WHERE b.id = ?",
        (bid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_budget(amount, budget_month, project_id=None, category_id=None, supplier='',
               expense_detail='', note='', attachment_path=None, attachment_name=None,
               submitter=''):
    conn = get_db()
    cursor = conn.execute('''
        INSERT INTO budgets (project_id, category_id, amount, supplier, expense_detail, note,
                             attachment_path, attachment_name, submitter, budget_month)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (project_id, category_id, amount, supplier, expense_detail, note,
          attachment_path, attachment_name, submitter, budget_month))
    conn.commit()
    bid = cursor.lastrowid
    conn.close()
    return bid


def update_budget(bid, **kwargs):
    """更新预算，支持部分更新"""
    allowed = ['project_id', 'category_id', 'amount', 'supplier', 'expense_detail',
               'note', 'attachment_path', 'attachment_name', 'submitter', 'payer',
               'payment_status', 'payment_date', 'payment_note', 'budget_month']
    fields = []
    values = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return
    fields.append("updated_at = datetime('now','localtime')")
    values.append(bid)
    conn = get_db()
    conn.execute(f"UPDATE budgets SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_budget(bid):
    """删除预算记录，同时删除关联附件文件"""
    conn = get_db()
    row = conn.execute("SELECT attachment_path FROM budgets WHERE id = ?", (bid,)).fetchone()
    if row and row['attachment_path']:
        filepath = row['attachment_path']
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
    conn.execute("DELETE FROM budgets WHERE id = ?", (bid,))
    conn.commit()
    conn.close()


# ==================== 统计查询 ====================

def get_overview_stats():
    """获取概览统计数据"""
    conn = get_db()
    stats = {}

    # 总支出（仅已支付）
    row = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM budgets WHERE payment_status = 'paid'").fetchone()
    stats['total_paid'] = round(row[0], 2)

    # 待支付总额
    row = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM budgets WHERE payment_status = 'pending'").fetchone()
    stats['total_pending'] = round(row[0], 2)

    # 总笔数
    row = conn.execute("SELECT COUNT(*) FROM budgets").fetchone()
    stats['total_count'] = row[0]

    # 已支付笔数
    row = conn.execute("SELECT COUNT(*) FROM budgets WHERE payment_status = 'paid'").fetchone()
    stats['paid_count'] = row[0]

    # 待支付笔数
    row = conn.execute("SELECT COUNT(*) FROM budgets WHERE payment_status = 'pending'").fetchone()
    stats['pending_count'] = row[0]

    # 活跃项目数
    row = conn.execute("SELECT COUNT(*) FROM projects WHERE status = 'active'").fetchone()
    stats['project_count'] = row[0]

    # 成员数
    row = conn.execute("SELECT COUNT(*) FROM members WHERE active = 1").fetchone()
    stats['member_count'] = row[0]

    conn.close()
    return stats


def get_monthly_trends(months=6):
    """获取最近N个月的支出趋势"""
    conn = get_db()
    rows = conn.execute('''
        SELECT budget_month, COALESCE(SUM(amount), 0) as total
        FROM budgets WHERE payment_status = 'paid'
        GROUP BY budget_month
        ORDER BY budget_month DESC
        LIMIT ?
    ''', (months,)).fetchall()
    conn.close()
    result = [{'month': r['budget_month'], 'total': round(r['total'], 2)} for r in rows]
    result.reverse()
    return result


def get_expense_by_category(month=None):
    """按分类汇总支出"""
    conn = get_db()
    query = '''
        SELECT c.name, c.icon, c.color, COALESCE(SUM(b.amount), 0) as total
        FROM budgets b LEFT JOIN categories c ON b.category_id = c.id
        WHERE b.payment_status = 'paid'
    '''
    params = []
    if month:
        query += " AND b.budget_month = ?"
        params.append(month)
    query += " GROUP BY b.category_id ORDER BY total DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [{'name': r['name'] or '未分类', 'icon': r['icon'] or '📌', 'color': r['color'] or '#B2BEC3', 'total': round(r['total'], 2)} for r in rows]


def get_expense_by_project():
    """按项目汇总支出（全部时间）"""
    conn = get_db()
    rows = conn.execute('''
        SELECT p.id, p.name, p.icon, p.color, COALESCE(SUM(b.amount), 0) as total
        FROM budgets b LEFT JOIN projects p ON b.project_id = p.id
        WHERE b.payment_status = 'paid'
        GROUP BY b.project_id ORDER BY total DESC
    ''').fetchall()
    conn.close()
    result = []
    for r in rows:
        if r['name']:
            result.append({'id': r['id'], 'name': r['name'], 'icon': r['icon'], 'color': r['color'], 'total': round(r['total'], 2)})
    return result


def get_available_months():
    """获取所有有数据的月份"""
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT budget_month FROM budgets ORDER BY budget_month").fetchall()
    conn.close()
    return [r['budget_month'] for r in rows]
