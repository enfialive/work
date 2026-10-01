#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wipo_weekly_fetch.py — 抓取 WIPO PATENTSCOPE 某周四（PCT 每周公开日）新公开的
IPC 分类为 A61 / C07（医药、化学领域）的 PCT 申请清单。

用法：
    python wipo_weekly_fetch.py                      # 默认取“最近一个周四”
    python wipo_weekly_fetch.py --date 2026-08-27    # 指定公开日（周四）
    python wipo_weekly_fetch.py --out ./reports      # 指定输出目录
    python wipo_weekly_fetch.py --delay 2.0          # 翻页间隔秒数（默认 1.5）

2026-10 改版适配（PATENTSCOPE 反爬升级）：
    - result.jsf?query=... 深链已失效（弹回检索首页），改为模拟高级检索页
      advancedSearchForm 的 PrimeFaces AJAX POST 拿重定向。
    - 结果页新增图片点选验证码（psCaptchaPanel，"Please select the picture with X"）。
      脚本检测到验证码时会把题目与 6 张图片存到 <输出目录>/_captcha/ 并保存会话状态，
      以退出码 42 退出。由 Claude（多模态）看图后运行：
          python wipo_weekly_fetch.py --date <公开日> --captcha-click <1-6>
      脚本提交点击；若进入新一轮验证码会再次以 42 退出并更新图片，重复直至通过，
      通过后自动继续翻页抓取并输出全部文件。

输出（写入 <out>/wipo_YYYY-MM-DD/）：
    publications.json   全量结构化数据
    publications.csv    便于 Excel 打开
    summary.txt         抓取摘要（总数、按 IPC 大组分布）

依赖：仅标准库。平台：Windows / Python 3.12。
"""

import argparse
import base64
import csv
import io
import json
import os
import pickle
import re
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar
from datetime import date, datetime, timedelta

BASE = "https://patentscope.wipo.int"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
QUERY_TMPL = "IC:C07 AND DP:{day:02d}.{month:02d}.{year}"
PAGE_SIZE = 10  # PATENTSCOPE 结果页固定每页 10 条
CAPTCHA_DIR = "_captcha"
EXIT_CAPTCHA = 42

RESULTS_COUNT_RE = re.compile(r'class="results-count">([\d,]+)\s+results')


def log(msg):
    print(msg, flush=True)


def strip_tags(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def most_recent_thursday(today=None):
    """返回最近一个周四（含今天，若今天即周四）。"""
    today = today or date.today()
    delta = (today.weekday() - 3) % 7  # 3 = 周四
    return today - timedelta(days=delta)


class CaptchaRequired(Exception):
    """结果页出现图片验证码，需要人工/模型介入。"""


class PatentscopeSession:
    def __init__(self, delay=1.5, retries=3):
        self.delay = delay
        self.retries = retries
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj))
        self.jsess = None
        self.viewstate = None
        self.page_form = None      # “Go to page”翻页表单 id
        self.page_form_action = None  # 翻页表单 action（新流程不带 jsessionid）
        self.captcha_action = None    # 验证码表单 action（result.jsf?_vid=...）

    # ---------- 基础请求 ----------

    def _get(self, url, timeout=90):
        last = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(url, headers=UA)
                return self.opener.open(req, timeout=timeout).read().decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                last = e
                # 403/405 多为限流，长退避
                wait = (30 * (attempt + 1) if "403" in str(e) or "405" in str(e)
                        else self.delay * (attempt + 2))
                log(f"  [重试 {attempt + 1}/{self.retries}] {e}；{wait:.0f}s 后重试")
                time.sleep(wait)
        raise RuntimeError(f"请求失败：{url}\n原因：{last}")

    def _post_ajax(self, url, data, timeout=120):
        """PrimeFaces partial/ajax POST，返回响应文本（不重试，由调用方处理）。"""
        req = urllib.request.Request(
            url, data=urllib.parse.urlencode(data).encode(),
            headers={**UA, "Faces-Request": "partial/ajax",
                     "Content-Type": "application/x-www-form-urlencoded",
                     "X-Requested-With": "XMLHttpRequest"})
        return self.opener.open(req, timeout=timeout).read().decode("utf-8", "replace")

    def _follow_redirect(self, resp, timeout=120):
        """partial-response 中的 <redirect> → GET 目标页。无 redirect 返回 None。"""
        m = re.search(r'<redirect url="([^"]+)"', resp)
        if not m:
            return None
        redir = urllib.parse.urljoin(BASE, m.group(1).replace("&amp;", "&"))
        return self._get(redir, timeout=timeout)

    # ---------- 检索 ----------

    def init_search(self, query):
        """发起检索，返回 (总条数, 第一页 HTML)。深链失效时自动走 POST 流程。"""
        url = (BASE + "/search/en/result.jsf?query=" + urllib.parse.quote(query)
               + "&office=&sortOption=Pub+Date+Desc&prevFilter=&maxRec=10")
        try:
            html = self._get(url)
        except RuntimeError as e:
            log(f"  result.jsf 深链请求失败（{e}），改用高级检索表单 POST 流程…")
            return self._init_search_via_post(query)
        m = RESULTS_COUNT_RE.search(html)
        if m:
            total = int(m.group(1).replace(",", ""))
            self._setup_from_results_page(html, total)
            return total, html
        if "No result" in html or "no result" in html:
            return 0, html
        if "psCaptchaPanel" in html:
            self._setup_captcha(html)
            raise CaptchaRequired()
        # 深链被弹回检索首页（2026-10 起）→ 走高级检索表单 POST
        log("  result.jsf 深链已失效，改用高级检索表单 POST 流程…")
        return self._init_search_via_post(query)

    def _init_search_via_post(self, query):
        adv = BASE + "/search/en/advancedSearch.jsf"
        page = self._get(adv)
        vs = re.search(
            r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', page)
        src = re.search(
            r'doSearch = function\(\) \{PrimeFaces\.ab\(\{s:"([^"]+)"', page)
        if not (vs and src):
            raise RuntimeError("高级检索页结构变化，未找到 ViewState/检索按钮")
        data = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": src.group(1),
            "javax.faces.partial.execute": "advancedSearchForm",
            "javax.faces.partial.render": "advancedSearchForm:advancedSearchInput",
            src.group(1): src.group(1),
            "advancedSearchForm": "advancedSearchForm",
            "advancedSearchForm:advancedSearchInput:input": query,
            "javax.faces.ViewState": vs.group(1),
        }
        resp = self._post_ajax(adv, data, timeout=180)
        html = self._follow_redirect(resp, timeout=240)
        if html is None:
            raise RuntimeError(f"检索 AJAX 未返回 redirect：{resp[:300]}")
        if "psCaptchaPanel" in html:
            self._setup_captcha(html)
            raise CaptchaRequired()
        m = RESULTS_COUNT_RE.search(html)
        if not m:
            if "No result" in html or "no result" in html:
                return 0, html
            raise RuntimeError("未能从结果页解析总条数，页面结构可能已变化")
        total = int(m.group(1).replace(",", ""))
        self._setup_from_results_page(html, total)
        return total, html

    def _setup_from_results_page(self, html, total):
        if total > 0:
            m = re.search(r"result\.jsf;(jsessionid=[^?&\"]+)", html)
            self.jsess = m.group(1) if m else None
            self.viewstate = re.search(
                r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html).group(1)
            # 定位“Go to page”翻页表单（组件 id 每次会话随机）
            self.page_form = None
            self.page_form_action = None
            for fid, action, body in re.findall(
                    r'<form id="(j_idt\d+:j_idt\d+)"[^>]*action="([^"]*)"[^>]*>(.*?)</form>',
                    html, re.S):
                if "ps-paginator-modal--input" in body:
                    self.page_form = fid
                    self.page_form_action = action.replace("&amp;", "&")
                    break
            if not self.page_form and total > PAGE_SIZE:
                raise RuntimeError("未找到翻页表单，页面结构可能已变化")

    # ---------- 验证码 ----------

    def _setup_captcha(self, html):
        m = re.search(r'<form id="psCaptchaForm"[^>]*action="([^"]+)"', html)
        self.captcha_action = (m.group(1).replace("&amp;", "&") if m
                               else "/search/en/result.jsf")
        vs = re.search(
            r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
        self.viewstate = vs.group(1) if vs else self.viewstate
        self._captcha_html = html

    def dump_captcha(self, capdir):
        """把验证码题目与图片写入 capdir。返回题目文本。"""
        os.makedirs(capdir, exist_ok=True)
        html = getattr(self, "_captcha_html", "")
        m = re.search(r'b-view-panel__section[^>]*>\s*(.*?)\s*</div>', html, re.S)
        question = strip_tags(m.group(1)) if m else "(未解析到题目)"
        with open(os.path.join(capdir, "question.txt"), "w", encoding="utf-8") as f:
            f.write(question + "\n")
        n = 0
        for idx, b64 in re.findall(
                r'<img id="image(\d)" src="data:image/png;base64,([^"]+)"', html):
            with open(os.path.join(capdir, f"img{idx}.png"), "wb") as f:
                f.write(base64.b64decode(b64))
            n += 1
        log(f"  验证码题目：{question}（{n} 张图片已存至 {capdir}）")
        return question

    def click_captcha(self, n):
        """提交第 n 张图片的点击。返回 'cleared' | 'again'。"""
        data = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": f"click{n}",
            "javax.faces.partial.execute": "psCaptchaForm",
            "javax.faces.partial.render": "psCaptchaPanel",
            f"click{n}": f"click{n}",
            "psCaptchaForm": "psCaptchaForm",
            "javax.faces.ViewState": self.viewstate,
        }
        url = urllib.parse.urljoin(BASE, self.captcha_action)
        resp = self._post_ajax(url, data, timeout=120)
        html = self._follow_redirect(resp, timeout=240)
        if html is not None:
            # 整页重定向：看结果页还是又一轮验证码
            if "psCaptchaPanel" in html:
                self._setup_captcha(html)
                return "again"
            self._after_html = html
            return "cleared"
        # 局部更新：解析 update 里的 CDATA
        m = re.search(
            r'<update id="psCaptchaPanel"><!\[CDATA\[(.*?)\]\]></update>', resp, re.S)
        panel = m.group(1) if m else resp
        if 'id="image1"' in panel or "ps-captcha" in panel:
            # 新一轮 / 答错重试：包一层壳复用 dump_captcha
            self._captcha_html = (
                panel + f'<form id="psCaptchaForm" action="{self.captcha_action}"></form>')
            return "again"
        # 面板无图片且无结果：尝试重新拉结果页
        html = self._get(urllib.parse.urljoin(BASE, self.captcha_action), timeout=240)
        if "psCaptchaPanel" in html:
            self._setup_captcha(html)
            return "again"
        self._after_html = html
        return "cleared"

    # ---------- 状态持久化（验证码跨进程接力） ----------

    def save_state(self, path, extra):
        state = {"cookies": list(self.cj), "viewstate": self.viewstate,
                 "jsess": self.jsess, "captcha_action": self.captcha_action,
                 "captcha_html": getattr(self, "_captcha_html", ""),
                 "delay": self.delay, **extra}
        with open(path, "wb") as f:
            pickle.dump(state, f)

    def load_state(self, path):
        with open(path, "rb") as f:
            state = pickle.load(f)
        for c in state["cookies"]:
            self.cj.set_cookie(c)
        self.viewstate = state.get("viewstate")
        self.jsess = state.get("jsess")
        self.captcha_action = state.get("captcha_action")
        self._captcha_html = state.get("captcha_html", "")
        self.delay = state.get("delay", self.delay)
        return state

    # ---------- 翻页 ----------

    def _post_ajax_goto(self, page):
        """PrimeFaces AJAX：跳转到指定页。返回该页 HTML。"""
        data = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": self.page_form + ":button",
            "javax.faces.partial.execute": self.page_form,
            "javax.faces.partial.render": "results-container @(.js-ps-global-messages)",
            self.page_form + ":button": self.page_form + ":button",
            self.page_form: self.page_form,
            self.page_form + ":input": str(page),
            "javax.faces.ViewState": self.viewstate,
        }
        # 优先带 _vid 的 URL：不带 _vid 时 JSF 可能恢复到错误视图，
        # 导致返回与请求页不符的重复页（2026-10-01 实测丢失 181 条）。
        url = None
        for cand in (self.page_form_action, self.captcha_action):
            if cand and "_vid=" in cand:
                url = urllib.parse.urljoin(BASE, cand)
                break
        if url is None:
            if self.page_form_action:
                url = urllib.parse.urljoin(BASE, self.page_form_action)
            else:
                url = f"{BASE}/search/en/result.jsf;{self.jsess}"
        last = None
        for attempt in range(self.retries):
            try:
                resp = self._post_ajax(url, data, timeout=90)
                html = self._follow_redirect(resp)
                if html is not None:
                    return html
                # 新流程可能直接返回 <update> 内联结果
                m = re.search(
                    r'<update id="results-container"><!\[CDATA\[(.*?)\]\]></update>',
                    resp, re.S)
                if m and "data-ri=" in m.group(1):
                    return m.group(1)
                raise RuntimeError(f"AJAX 响应中无 redirect/结果：{resp[:200]}")
            except Exception as e:  # noqa: BLE001
                last = e
                wait = (30 * (attempt + 1) if "403" in str(e) or "405" in str(e)
                        else self.delay * (attempt + 2))
                log(f"  [翻页重试 {attempt + 1}/{self.retries}] {e}；{wait:.0f}s 后重试")
                time.sleep(wait)
        raise RuntimeError(f"第 {page} 页获取失败：{last}")

    def fetch_page(self, page, seen_ids=None):
        """page 从 1 开始；第 1 页由 init_search 返回。
        seen_ids 传入已抓 doc_id 集合时做整页重复检测，命中则重试。"""
        for attempt in range(3):
            html = self._post_ajax_goto(page)
            time.sleep(self.delay)
            if seen_ids is None:
                return html
            ids = set(re.findall(r'data-rk="([^"]+)"', html))
            if not ids or not ids.issubset(seen_ids):
                return html
            log(f"  第 {page} 页返回整页重复内容，重试 ({attempt + 1}/3)…")
            time.sleep(self.delay * 2)
        raise RuntimeError(f"第 {page} 页连续返回重复内容")


FIELD_RE = re.compile(
    r'ps-field--label[^>]*>\s*(.*?)\s*</span>\s*'
    r'<span[^>]*class="[^"]*ps-field--value[^"]*"[^>]*>(.*?)</span>', re.S)


def parse_rows(html):
    """解析结果列表页，返回记录列表。"""
    records = []
    for block in html.split("<tr data-ri=")[1:]:
        rec = {}
        m = re.search(r'data-rk="([^"]+)"', block)
        if not m:
            continue
        rec["doc_id"] = m.group(1)                       # 如 WO2026177342
        m = re.search(r'data-mt-ipc="([^"]*)"', block)
        rec["ipc_main"] = m.group(1).strip() if m else ""  # 如 A61K 47/00
        m = re.search(r'ps-patent-result--title--patent-number">([^<]+)<', block)
        rec["publication_number"] = m.group(1).strip() if m else ""  # WO/2026/177342
        m = re.search(r'needTranslation-title[^>]*>(.*?)</span>\s*</span>', block, re.S)
        rec["title"] = strip_tags(m.group(1)) if m else ""
        m = re.search(r'resultListTableColumnPubDate[^>]*>([^<]+)<', block)
        rec["publication_date"] = m.group(1).strip() if m else ""    # DD.MM.YYYY
        for label, value in FIELD_RE.findall(block):
            label = strip_tags(label).rstrip(".")
            value = strip_tags(value)
            if label == "Int.Class":
                rec["ipc_all"] = value
            elif label == "Appl.No":
                rec["application_number"] = value
            elif label == "Applicant":
                rec["applicant"] = value
            elif label == "Inventor":
                rec["inventor"] = value
        rec["link"] = f"{BASE}/search/en/detail.jsf?docId={rec['doc_id']}"
        records.append(rec)
    return records


def ipc_group(ipc):
    """取 IPC 大组前缀，如 'A61K 47/00' -> 'A61K'。"""
    m = re.match(r"([A-HY]\d{2}[A-Z])", ipc.strip())
    return m.group(1) if m else "其他"


def _write_json(path, pub_day, query, total, records, partial=False):
    payload = {"publication_day": pub_day.isoformat(), "query": query,
               "total_official": total, "total_fetched": len(records),
               "records": records}
    if partial:
        payload["partial"] = True
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def fetch_all(sess, query, total, html, out_dir, pub_day):
    """翻页抓全量并写出 publications.json/csv/summary.txt。"""
    json_path = f"{out_dir}/publications.json"
    records = parse_rows(html)
    seen_ids = {r["doc_id"] for r in records}
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    bad_pages = []
    log(f"共 {pages} 页，开始翻页抓取（约 {pages * (sess.delay + 1) / 60:.0f} 分钟）…")
    for p in range(2, pages + 1):
        try:
            html = sess.fetch_page(p, seen_ids=seen_ids)
        except RuntimeError as e:
            log(f"  {e}；等待 60s 后重建会话从第 {p} 页继续")
            time.sleep(60)
            try:
                new_sess = PatentscopeSession(delay=sess.delay)
                new_sess.init_search(query)
                sess = new_sess
                html = sess.fetch_page(p, seen_ids=seen_ids)
            except CaptchaRequired:
                os.makedirs(f"{out_dir}/{CAPTCHA_DIR}", exist_ok=True)
                sess.save_state(f"{out_dir}/{CAPTCHA_DIR}/state.pkl", {})
                sess.dump_captcha(f"{out_dir}/{CAPTCHA_DIR}")
                _write_json(json_path, pub_day, query, total, records, partial=True)
                log("重建会话时又遇验证码，部分结果已存盘；请解验证码后用 "
                    "--captcha-click N 重跑（将从头翻页）。")
                sys.exit(EXIT_CAPTCHA)
            except RuntimeError as e2:
                log(f"  第 {p} 页最终失败：{e2}；该页 10 条缺失，稍后需补抓")
                bad_pages.append(p)
                continue
        rows = parse_rows(html)
        records.extend(rows)
        seen_ids.update(r["doc_id"] for r in rows)
        if p % 10 == 0 or p == pages:
            log(f"  进度：第 {p}/{pages} 页，累计 {len(records)} 条")
            _write_json(json_path, pub_day, query, total, records, partial=True)

    # 去重（同一 docId 可能因翻页边界重复）
    seen, uniq = set(), []
    for r in records:
        if r["doc_id"] not in seen:
            seen.add(r["doc_id"])
            uniq.append(r)
    records = uniq
    log(f"抓取完成，去重后 {len(records)} 条（官方计数 {total}）")
    if len(records) < total or bad_pages:
        log(f"⚠️ 缺 {total - len(records)} 条；失败页：{bad_pages or '无（疑似重复页未补齐）'}"
            "——报告需注明口径缺口或补抓")

    # 按 IPC 大组统计
    from collections import Counter
    dist = Counter(ipc_group(r.get("ipc_main", "")) for r in records)

    _write_json(json_path, pub_day, query, total, records)

    with open(f"{out_dir}/publications.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "publication_number", "title", "applicant", "inventor",
            "ipc_main", "ipc_all", "application_number",
            "publication_date", "doc_id", "link"])
        w.writeheader()
        w.writerows(records)

    with open(f"{out_dir}/summary.txt", "w", encoding="utf-8") as f:
        f.write(f"WIPO PCT 新公开（C07）抓取摘要\n")
        f.write(f"公开日：{pub_day}（周四）\n检索式：{query}\n")
        f.write(f"官方计数：{total}；实抓：{len(records)}\n")
        if bad_pages:
            f.write(f"⚠️ 失败页（每页10条缺失）：{bad_pages}\n")
        f.write("\nIPC 大组分布：\n")
        for g, n in dist.most_common():
            f.write(f"  {g}: {n}\n")

    log(f"输出目录：{out_dir}")
    log("IPC 大组分布：" + ", ".join(f"{g}:{n}" for g, n in dist.most_common(10)))


def main():
    ap = argparse.ArgumentParser(description="抓取 WIPO 每周四新公开的 A61/C07 类 PCT 申请")
    ap.add_argument("--date", help="公开日（周四），格式 YYYY-MM-DD；默认取最近一个周四")
    ap.add_argument("--out", default="wipo_reports", help="输出根目录（默认 ./wipo_reports）")
    ap.add_argument("--delay", type=float, default=1.5, help="请求间隔秒数（默认 1.5）")
    ap.add_argument("--captcha-click", type=int, metavar="N",
                    help="验证码接力：点击第 N 张图（1-6）后继续抓取；"
                         "状态从 <out>/wipo_<date>/_captcha/state.pkl 读取")
    args = ap.parse_args()

    if args.date:
        pub_day = datetime.strptime(args.date, "%Y-%m-%d").date()
        if pub_day.weekday() != 3:
            log(f"警告：{pub_day} 不是周四，PCT 一般在周四公开，请确认日期。")
    else:
        pub_day = most_recent_thursday()

    query = QUERY_TMPL.format(day=pub_day.day, month=pub_day.month, year=pub_day.year)
    log(f"目标公开日：{pub_day}（周四）")
    log(f"检索式：{query}")

    out_dir = f"{args.out}/wipo_{pub_day.isoformat()}"
    os.makedirs(out_dir, exist_ok=True)
    capdir = os.path.join(out_dir, CAPTCHA_DIR)
    state_path = os.path.join(capdir, "state.pkl")

    sess = PatentscopeSession(delay=args.delay)

    if args.captcha_click:
        # —— 验证码接力模式 ——
        if not os.path.exists(state_path):
            log(f"未找到验证码状态文件：{state_path}，请先正常运行脚本触发验证码。")
            sys.exit(2)
        sess.load_state(state_path)
        log(f"提交验证码点击：第 {args.captcha_click} 张图…")
        outcome = sess.click_captcha(args.captcha_click)
        if outcome == "again":
            sess.save_state(state_path, {})
            sess.dump_captcha(capdir)
            log("验证码未通过/进入新一轮，图片已更新。请重新看图后用 "
                f"--captcha-click N 再试。")
            sys.exit(EXIT_CAPTCHA)
        # 通过：结果页已在 sess._after_html
        html = sess._after_html
        m = RESULTS_COUNT_RE.search(html)
        if not m:
            raise RuntimeError("验证码已通过但结果页解析失败，请人工检查。")
        total = int(m.group(1).replace(",", ""))
        log(f"验证码通过！命中总数：{total}")
        sess._setup_from_results_page(html, total)
        fetch_all(sess, query, total, html, out_dir, pub_day)
        # 清理验证码状态
        for f in os.listdir(capdir):
            os.remove(os.path.join(capdir, f))
        os.rmdir(capdir)
        return

    # —— 正常模式 ——
    try:
        total, html = sess.init_search(query)
    except CaptchaRequired:
        os.makedirs(capdir, exist_ok=True)
        sess.save_state(state_path, {})
        question = sess.dump_captcha(capdir)
        log("")
        log("=" * 60)
        log("PATENTSCOPE 触发了图片验证码，需要人工/模型识别：")
        log(f"  1. 查看 {capdir}/question.txt 与 img1.png … img6.png")
        log(f"  2. 确定答案图片序号 N 后运行：")
        log(f"     python {os.path.basename(__file__)} --date {pub_day.isoformat()}"
            f" --captcha-click N")
        log("=" * 60)
        sys.exit(EXIT_CAPTCHA)

    log(f"命中总数：{total}")

    if total == 0:
        log("本周该公开日无 A61/C07 类新公开（或公开日遇节假日顺延，可换日期重试）。")
        with open(f"{out_dir}/publications.json", "w", encoding="utf-8") as f:
            json.dump({"publication_day": pub_day.isoformat(), "query": query,
                       "total": 0, "records": []}, f, ensure_ascii=False, indent=2)
        return

    fetch_all(sess, query, total, html, out_dir, pub_day)


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
