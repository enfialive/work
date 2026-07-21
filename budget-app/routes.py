# -*- coding: utf-8 -*-
"""
API 路由层 - 所有 RESTful API 接口
"""

import os
import uuid
import csv
import io
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, Response

import models

api = Blueprint('api', __name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file):
    """保存上传文件，返回 (文件路径, 原始文件名)"""
    if not file or file.filename == '':
        return None, None
    if not allowed_file(file.filename):
        raise ValueError(f'不支持的文件类型，仅支持: {", ".join(ALLOWED_EXTENSIONS)}')

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        raise ValueError('文件大小超过 10MB 限制')

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = file.filename.rsplit('.', 1)[1].lower()
    new_name = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, new_name)
    file.save(filepath)
    return filepath, file.filename


# ==================== 成员管理 ====================

@api.route('/members', methods=['GET'])
def list_members():
    members = models.get_all_members()
    return jsonify(members)


@api.route('/members', methods=['POST'])
def create_member():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '成员姓名不能为空'}), 400
    name = data['name'].strip()
    role = data.get('role', 'member')
    if role not in ('member', 'payer'):
        return jsonify({'error': '角色必须是 member 或 payer'}), 400
    mid = models.add_member(name, role)
    return jsonify({'id': mid, 'name': name, 'role': role}), 201


@api.route('/members/<int:mid>', methods=['PUT'])
def update_member(mid):
    data = request.get_json()
    if not data:
        return jsonify({'error': '无更新数据'}), 400
    models.update_member(mid,
                         name=data.get('name', '').strip() or None,
                         role=data.get('role'))
    return jsonify({'ok': True})


@api.route('/members/<int:mid>', methods=['DELETE'])
def delete_member(mid):
    models.delete_member(mid)
    return jsonify({'ok': True})


# ==================== 分类管理 ====================

@api.route('/categories', methods=['GET'])
def list_categories():
    cats = models.get_all_categories()
    return jsonify(cats)


@api.route('/categories', methods=['POST'])
def create_category():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '分类名称不能为空'}), 400
    cid = models.add_category(
        name=data['name'].strip(),
        icon=data.get('icon', '📌'),
        color=data.get('color', '#4A90D9')
    )
    return jsonify({'id': cid}), 201


@api.route('/categories/<int:cid>', methods=['PUT'])
def update_category(cid):
    data = request.get_json()
    if not data:
        return jsonify({'error': '无更新数据'}), 400
    models.update_category(cid,
                           name=data.get('name', '').strip() or None,
                           icon=data.get('icon'),
                           color=data.get('color'))
    return jsonify({'ok': True})


@api.route('/categories/<int:cid>', methods=['DELETE'])
def delete_category(cid):
    models.delete_category(cid)
    return jsonify({'ok': True})


# ==================== 项目分组管理 ====================

@api.route('/project-groups', methods=['GET'])
def list_project_groups():
    groups = models.get_all_project_groups()
    return jsonify(groups)


@api.route('/project-groups', methods=['POST'])
def create_project_group():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '分组名称不能为空'}), 400
    gid = models.add_project_group(
        name=data['name'].strip(),
        icon=data.get('icon', '📂'),
        color=data.get('color', '#6C5CE7')
    )
    return jsonify({'id': gid}), 201


@api.route('/project-groups/<int:gid>', methods=['PUT'])
def update_project_group(gid):
    data = request.get_json()
    if not data:
        return jsonify({'error': '无更新数据'}), 400
    models.update_project_group(gid,
                                name=data.get('name', '').strip() or None,
                                icon=data.get('icon'),
                                color=data.get('color'))
    return jsonify({'ok': True})


@api.route('/project-groups/<int:gid>', methods=['DELETE'])
def delete_project_group(gid):
    models.delete_project_group(gid)
    return jsonify({'ok': True})


@api.route('/project-groups/reorder', methods=['PUT'])
def reorder_project_groups():
    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({'error': '请求格式不正确'}), 400
    models.reorder_project_groups(data)
    return jsonify({'ok': True})


# ==================== 项目管理 ====================

@api.route('/projects', methods=['GET'])
def list_projects():
    projects = models.get_all_projects()
    return jsonify(projects)


@api.route('/projects', methods=['POST'])
def create_project():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '项目名称不能为空'}), 400
    pid = models.add_project(
        name=data['name'].strip(),
        description=data.get('description', ''),
        icon=data.get('icon', '📁'),
        color=data.get('color', '#4A90D9'),
        group_id=data.get('group_id')
    )
    return jsonify({'id': pid}), 201


@api.route('/projects/<int:pid>', methods=['PUT'])
def update_project(pid):
    data = request.get_json()
    if not data:
        return jsonify({'error': '无更新数据'}), 400
    kwargs = dict(
        name=data.get('name', '').strip() or None,
        description=data.get('description'),
        icon=data.get('icon'),
        color=data.get('color'),
        status=data.get('status'))
    # group_id may be explicitly null (to unset), use sentinel
    if 'group_id' in data:
        kwargs['_set_group_id'] = data['group_id']
    models.update_project(pid, **kwargs)
    return jsonify({'ok': True})


@api.route('/projects/<int:pid>', methods=['DELETE'])
def delete_project(pid):
    models.delete_project(pid)
    return jsonify({'ok': True})


@api.route('/projects/reorder', methods=['PUT'])
def reorder_projects():
    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({'error': '请求格式不正确'}), 400
    models.reorder_projects(data)
    return jsonify({'ok': True})


# ==================== 供应商管理 ====================

@api.route('/suppliers', methods=['GET'])
def list_suppliers():
    suppliers = models.get_all_suppliers()
    return jsonify(suppliers)


@api.route('/suppliers', methods=['POST'])
def create_supplier():
    data = request.get_json()
    if not data or not data.get('name', '').strip():
        return jsonify({'error': '供应商名称不能为空'}), 400
    sid = models.add_supplier(
        name=data['name'].strip(),
        contact=data.get('contact', ''),
        note=data.get('note', ''),
        contract_signed=1 if data.get('contract_signed') else 0
    )
    return jsonify({'id': sid}), 201


@api.route('/suppliers/<int:sid>', methods=['PUT'])
def update_supplier(sid):
    data = request.get_json()
    if not data:
        return jsonify({'error': '无更新数据'}), 400
    models.update_supplier(sid,
                           name=data.get('name', '').strip() or None,
                           contact=data.get('contact'),
                           note=data.get('note'),
                           contract_signed=1 if data.get('contract_signed') else 0 if 'contract_signed' in data else None)
    return jsonify({'ok': True})


@api.route('/suppliers/<int:sid>', methods=['DELETE'])
def delete_supplier(sid):
    models.delete_supplier(sid)
    return jsonify({'ok': True})


# ==================== 预算管理（核心） ====================

@api.route('/budgets', methods=['GET'])
def list_budgets():
    status = request.args.get('status', 'all')
    month = request.args.get('month', 'all')
    project_id = request.args.get('project_id', 'all')
    category_id = request.args.get('category_id', 'all')
    keyword = request.args.get('keyword', '').strip() or None

    budgets = models.get_all_budgets(
        status=status,
        month=month,
        project_id=project_id,
        category_id=category_id,
        keyword=keyword
    )
    return jsonify(budgets)


@api.route('/budgets', methods=['POST'])
def create_budget():
    """创建预算（支持文件上传）"""
    amount = request.form.get('amount', '').strip()
    budget_month = request.form.get('budget_month', '').strip()
    project_id = request.form.get('project_id', '').strip()
    category_id = request.form.get('category_id', '').strip()
    supplier = request.form.get('supplier', '').strip()
    expense_detail = request.form.get('expense_detail', '').strip()
    note = request.form.get('note', '').strip()
    submitter = request.form.get('submitter', '').strip()

    if not amount:
        return jsonify({'error': '金额不能为空'}), 400
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except ValueError:
        return jsonify({'error': '金额必须为正数'}), 400

    if not budget_month:
        return jsonify({'error': '预算月份不能为空'}), 400

    project_id = int(project_id) if project_id else None
    category_id = int(category_id) if category_id else None

    # 处理附件
    attachment_path = None
    attachment_name = None
    file = request.files.get('attachment')
    if file and file.filename:
        try:
            attachment_path, attachment_name = save_upload(file)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

    bid = models.add_budget(
        amount=amount,
        budget_month=budget_month,
        project_id=project_id,
        category_id=category_id,
        supplier=supplier,
        expense_detail=expense_detail,
        note=note,
        attachment_path=attachment_path,
        attachment_name=attachment_name,
        submitter=submitter
    )
    return jsonify({'id': bid}), 201


@api.route('/budgets/<int:bid>', methods=['PUT'])
def update_budget(bid):
    """更新预算（支持文件上传和支付状态变更）"""
    existing = models.get_budget_by_id(bid)
    if not existing:
        return jsonify({'error': '记录不存在'}), 404

    updates = {}

    # 处理表单字段
    for field in ['amount', 'budget_month', 'project_id', 'category_id',
                  'supplier', 'expense_detail', 'note', 'submitter',
                  'payer', 'payment_status', 'payment_date', 'payment_note']:
        val = request.form.get(field, '').strip()
        if val:
            if field in ('amount',):
                try:
                    updates[field] = float(val)
                except ValueError:
                    return jsonify({'error': f'{field} 格式不正确'}), 400
            elif field in ('project_id', 'category_id'):
                updates[field] = int(val) if val else None
            else:
                updates[field] = val

    # 处理附件
    file = request.files.get('attachment')
    if file and file.filename:
        try:
            # 删除旧附件
            if existing.get('attachment_path') and os.path.exists(existing['attachment_path']):
                try:
                    os.remove(existing['attachment_path'])
                except OSError:
                    pass
            new_path, new_name = save_upload(file)
            updates['attachment_path'] = new_path
            updates['attachment_name'] = new_name
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

    if updates:
        models.update_budget(bid, **updates)

    return jsonify({'ok': True})


@api.route('/budgets/<int:bid>', methods=['DELETE'])
def delete_budget(bid):
    models.delete_budget(bid)
    return jsonify({'ok': True})


@api.route('/budgets/<int:bid>/attachment', methods=['GET'])
def download_attachment(bid):
    """下载/预览附件"""
    budget = models.get_budget_by_id(bid)
    if not budget or not budget.get('attachment_path'):
        return jsonify({'error': '附件不存在'}), 404

    filepath = budget['attachment_path']
    if not os.path.exists(filepath):
        return jsonify({'error': '附件文件已丢失'}), 404

    return send_file(filepath, download_name=budget.get('attachment_name', 'attachment'))


# ==================== 统计接口 ====================

@api.route('/stats/overview', methods=['GET'])
def overview_stats():
    stats = models.get_overview_stats()
    trends = models.get_monthly_trends(6)
    by_category = models.get_expense_by_category()
    by_project = models.get_expense_by_project()
    months = models.get_available_months()

    return jsonify({
        'stats': stats,
        'trends': trends,
        'by_category': by_category,
        'by_project': by_project,
        'available_months': months
    })


@api.route('/stats/project/<int:pid>', methods=['GET'])
def project_stats(pid):
    """单个项目的支出统计"""
    budgets = models.get_all_budgets(project_id=pid, status='paid')
    total = sum(b['amount'] for b in budgets)

    # 按分类汇总
    cat_map = {}
    for b in budgets:
        cname = b.get('category_name', '未分类')
        if cname not in cat_map:
            cat_map[cname] = {'name': cname, 'icon': b.get('category_icon', '📌'),
                              'color': b.get('category_color', '#B2BEC3'), 'total': 0}
        cat_map[cname]['total'] += b['amount']

    return jsonify({
        'project_id': pid,
        'total_expense': round(total, 2),
        'record_count': len(budgets),
        'by_category': sorted(cat_map.values(), key=lambda x: x['total'], reverse=True)
    })


# ==================== 数据管理 ====================

@api.route('/export/csv', methods=['POST'])
def export_csv():
    """导出筛选后的 CSV"""
    data = request.get_json() or {}
    budgets = models.get_all_budgets(
        status=data.get('status', 'all'),
        month=data.get('month', 'all'),
        project_id=data.get('project_id', 'all')
    )

    output = io.StringIO()
    output.write('﻿')  # BOM for Excel
    writer = csv.writer(output)
    writer.writerow(['ID', '月份', '项目', '分类', '金额', '供应商', '费用明细', '备注',
                     '提交人', '支付人', '支付状态', '支付日期', '支付备注', '创建时间'])

    status_map = {'pending': '待支付', 'paid': '已支付', 'failed': '支付失败'}
    for b in budgets:
        writer.writerow([
            b['id'], b['budget_month'],
            b.get('project_name', '') or '',
            b.get('category_name', '未分类') or '未分类',
            b['amount'], b.get('supplier', ''), b.get('expense_detail', ''),
            b.get('note', ''), b.get('submitter', ''), b.get('payer', ''),
            status_map.get(b.get('payment_status', ''), b.get('payment_status', '')),
            b.get('payment_date', ''), b.get('payment_note', ''),
            b.get('created_at', '')
        ])

    csv_content = output.getvalue()
    output.close()

    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=budget_export_{datetime.now().strftime("%Y%m%d")}.csv'}
    )


@api.route('/export/json', methods=['POST'])
def export_json():
    """导出完整数据备份"""
    data = {
        'version': 1,
        'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'members': models.get_all_members(),
        'categories': models.get_all_categories(),
        'projects': models.get_all_projects(),
        'budgets': models.get_all_budgets()
    }
    return jsonify(data)


@api.route('/import/json', methods=['POST'])
def import_json():
    """导入 JSON 备份"""
    if 'file' not in request.files:
        return jsonify({'error': '请上传备份文件'}), 400

    file = request.files['file']
    try:
        data = json.loads(file.read().decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return jsonify({'error': '文件格式不正确'}), 400

    if 'version' not in data:
        return jsonify({'error': '备份文件格式不正确'}), 400

    # 清除现有数据并导入
    conn = models.get_db()
    try:
        conn.execute("DELETE FROM budgets")
        conn.execute("DELETE FROM projects")
        conn.execute("DELETE FROM categories")
        conn.execute("DELETE FROM members")

        for m in data.get('members', []):
            conn.execute("INSERT INTO members (id, name, role, active, created_at) VALUES (?, ?, ?, ?, ?)",
                         (m['id'], m['name'], m.get('role', 'member'), m.get('active', 1), m.get('created_at', '')))
        for c in data.get('categories', []):
            conn.execute("INSERT INTO categories (id, name, icon, color, created_at) VALUES (?, ?, ?, ?, ?)",
                         (c['id'], c['name'], c.get('icon', '📌'), c.get('color', '#4A90D9'), c.get('created_at', '')))
        for p in data.get('projects', []):
            conn.execute("INSERT INTO projects (id, name, description, icon, color, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (p['id'], p['name'], p.get('description', ''), p.get('icon', '📁'), p.get('color', '#4A90D9'),
                          p.get('status', 'active'), p.get('created_at', '')))
        for b in data.get('budgets', []):
            conn.execute('''INSERT INTO budgets (id, project_id, category_id, amount, supplier, expense_detail, note,
                           attachment_path, attachment_name, submitter, payer, payment_status, payment_date,
                           payment_note, budget_month, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                         (b['id'], b.get('project_id'), b.get('category_id'), b['amount'], b.get('supplier', ''),
                          b.get('expense_detail', ''), b.get('note', ''), b.get('attachment_path'),
                          b.get('attachment_name'), b.get('submitter', ''), b.get('payer', ''),
                          b.get('payment_status', 'pending'), b.get('payment_date'), b.get('payment_note', ''),
                          b.get('budget_month', ''), b.get('created_at', ''), b.get('updated_at', '')))
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'message': f"已导入 {len(data.get('budgets', []))} 条预算记录"})
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': f'导入失败: {str(e)}'}), 500
