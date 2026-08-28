#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_weekly.py — 对 wipo_weekly_fetch.py 的输出做二级分析：
1. 按药物类型自动初分（小分子/大分子/细胞基因与核酸/疫苗/制剂/器械诊断/其他）
2. 从标题识别明确出现的药物靶点
3. 统计重点申请人
4. 生成分组全量清单 markdown（供拼入周报）

用法：
    python analyze_weekly.py wipo_reports/wipo_2026-08-27
输出：
    <目录>/analysis.json     每条记录附加 category / targets 字段 + 各项统计
    <目录>/listing.md        按类别+IPC 大组分组的全量清单
注意：分类仅基于第一 IPC 分类与标题关键词，属初筛口径，个例可能误分。
"""

import json
import re
import sys
import io
from collections import Counter, defaultdict

# ---------------- 药物类型分类规则 ----------------
# 用户口径（顺序敏感，先命中先生效）：
#   化学药小分子 / 抗体 / 抗体偶联物(ADC) / 小核酸 / CAR-T / 抗体平台 /
#   多肽/短肽 / 偶联单元(毒素连接子) / 其他偶联类(PDC、AOC、APC等) / 其他
# 标题规则优先于 IPC 规则。

TITLE_RULES = [
    ("CAR-T", r"\bcar[\s-]?t\b|\bcar[\s-]?nk\b|\btcr[\s-]?t\b|chimeric antigen receptor"),
    ("小核酸", r"\bsirna\b|\bshrna\b|\bmirna\b|\bsarna\b|\brnai\b|\baso\b|"
     r"antisense|oligonucleotide|aptamer|guide rna|nucleic acid molecule|"
     r"\bmrna\b(?! binding)|rna nanostructure"),
    ("偶联单元（毒素/连接子）", r"linker|payload|warhead|toxin moiety|chelat|"
     r"self-immolative|drug-linker"),
    ("抗体偶联物（ADC）", r"antibod[a-z\- ]*drug conjugate|\badc\b|immuno-?conjugate"),
    ("偶联单元（毒素/连接子）", r"drug conjugates?\b"),
    ("其他偶联类", r"conjugat|\bpdc\b|\baoc\b|\bapc\b|radionuclide|radioligand"),
    ("抗体平台", r"(antibod|nanobod|vhh|immunoglobulin|phage display|yeast display|"
     r"b[- ]cell)[a-z ]*(librar|display|screen|discover|platform|identif|select|"
     r"produc|prepar|purif|humaniz|transgenic|repertoire|sequenc)|"
     r"(librar|display)[a-z ]*(identif|screen|discover)[a-z ]*"
     r"(antibod|peptide|polypeptide|protein|modulator)"),
    ("抗体", r"antibod|\bmabs?\b|nanobod|\bvhh\b|\bscfv\b|immunoglobulin|"
     r"[a-z]+specific\b|fc[- ]fusion|single[- ]domain"),
    ("多肽/短肽", r"peptide|polypeptide|fusion protein|\bprotein\b|enzyme|"
     r"hormone|albumin|cytokine|growth factor"),
    ("化学药小分子", r"inhibitor|antagonist|agonist|modulator|degrader|protac|"
     r"molecular glue|compound|derivative|prodrug|salt\s+thereof|crystal|"
     r"polymorph|small molecule|heterocyclic"),
]

IPC_RULES = [
    ("抗体偶联物（ADC）", r"^A61K\s*47/68"),
    ("小核酸", r"^A61K\s*48|^C12N\s*15"),
    ("抗体", r"^C07K\s*16"),
    ("多肽/短肽", r"^C07K"),
    ("化学药小分子", r"^C07[CDEFGHJ]|^A61K\s*31"),
]

CATEGORIES = ["化学药小分子", "抗体", "抗体偶联物（ADC）", "小核酸", "CAR-T",
              "抗体平台", "多肽/短肽", "偶联单元（毒素/连接子）", "其他偶联类", "其他"]

# 需要靶点覆盖的类别（用户指定）；其余类别不做靶点提取
TARGET_CATEGORIES = {"化学药小分子", "抗体", "抗体偶联物（ADC）", "多肽/短肽", "CAR-T"}

# 清单中折叠的类别（非药品/非早期研发，只留计数）
COLLAPSED_CATEGORIES = {"其他"}


def classify(rec):
    title = rec.get("title", "")
    ipc = rec.get("ipc_main", "")
    for cat, pat in TITLE_RULES:
        if re.search(pat, title, re.I):
            return cat
    for cat, pat in IPC_RULES:
        if re.search(pat, ipc, re.I):
            return cat
    return "其他"


# ---------------- 靶点词表 ----------------
# 常见药物靶点（标题级识别，词表可扩充）
TARGETS = [
    # 肿瘤免疫
    "PD-1", "PD-L1", "PD-L2", "CTLA-4", "TIGIT", "LAG-3", "TIM-3", "OX40",
    "4-1BB", "CD47", "SIRP", "STING", "A2A", "adenosine receptor",
    # 肿瘤靶点
    "HER2", "HER3", "EGFR", "ALK", "ROS1", "KRAS", "BRAF", "MEK", "RAF",
    "CDK2", "CDK4", "CDK6", "CDK7", "CDK9", "CDK12", "PARP", "BCL-2", "BCL-XL",
    "MCL-1", "MDM2", "BTK", "JAK1", "JAK2", "JAK3", "TYK2", "PI3K", "AKT",
    "mTOR", "VEGF", "VEGFR", "FGFR", "MET", "c-MET", "RET", "NTRK", "AXL",
    "SRC", "ABL", "FLT3", "IDH1", "IDH2", "EZH2", "BET", "BRD4", "HDAC",
    "WEE1", "ATR", "ATM", "CHK1", "PLK", "Aurora", "MYC", "RAS", "SHP2",
    "SOS1", "USP1", "WRN", "PRMT5", "MAT2A", "KAT6", "menin", "PIM",
    # 代谢/内分泌
    "GLP-1", "GIP", "glucagon", "GCG", "insulin", "amylin", "SGLT2", "SGLT1",
    "DPP-4", "PCSK9", "FGF21", "THR", "ACC", "DGAT", "ApoC", "ANGPTL3",
    "LP(a)", "CETP", "PPAR", "FXR", "GCGR", "GIPR", "GLP1R",
    # 免疫炎症
    "TNF", "IL-1", "IL-2", "IL-4", "IL-5", "IL-6", "IL-7", "IL-10", "IL-12",
    "IL-13", "IL-15", "IL-17", "IL-23", "IL-33", "IL-36", "TSLP", "BAFF",
    "APRIL", "ROR", "IRAK4", "NLRP3", "S1P", "integrin", "selectin",
    "FcRn", "Fc gamma", "complement", "C5a", "C3b",
    # 神经/精神
    "amyloid", "tau", "alpha-synuclein", "LRRK2", "TDP-43", " huntingtin",
    "dopamine", "serotonin", "5-HT", "GABA", "NMDA", "AMPA", "orexin",
    "mu opioid", "MOR", "KOR", "Nav1.", "Kv7", "TRP", "P2X", "sigma",
    # 血液/心血管
    "factor X", "factor XI", "thrombin", "TPA", "GPVI", "vWF", "S1PR",
    "endothelin", "renin", "ACE2", "NEP ", "sGC", "myosin", "troponin",
    # 感染
    "neuraminidase", "protease", "polymerase", "integrase", "reverse transcriptase",
    "spike protein", "capsid", "helicase", "gyrase", "penicillin-binding",
    # 细胞表面分子（抗体靶点）
    "CD19", "CD20", "CD22", "CD30", "CD38", "CD40", "CD3", "CD5", "CD7",
    "BCMA", "GPRC5D", "FcRH5", "TROP2", "Trop-2", "nectin-4", "claudin",
    "CLDN", "DLL3", "B7-H3", "B7-H4", "MSLN", "mesothelin", "CEA", "CEACAM",
    "PSMA", "FAP", "EpCAM", "MUC1", "GPC3", "ROR1", "ROR2", "LIV-1",
    "folate receptor", "FR alpha", "transferrin receptor",
    # 其他
    "growth hormone", "erythropoietin", "EPO", "G-CSF", "FSH", "LH",
    "GnRH", "somatostatin", "vasopressin", "oxytocin", "calcitonin",
    "RANKL", "sclerostin", "BMP", "WNT", "hedgehog", "notch", "TGF",
    "SMAD", "HIF", "Nrf2", "AhR", "TLR", "cGAS", "RIG-I", "MAVS",
]

# 预编译：长词优先，避免 "CDK4" 命中前先中 "RAS" 之类
_TARGET_RES = []
for t in sorted(set(TARGETS), key=len, reverse=True):
    _TARGET_RES.append((t, re.compile(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![a-z])(?!\s*-?\s*like)", re.I)))

# 通用模式："<X> inhibitor/antagonist/agonist" 中的 X
GENERIC_TARGET_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9]{1,15}(?:[-/][A-Za-z0-9]{1,10})?)\s+"
    r"(?:inhibitor|antagonist|agonist|modulator|degrader|blocker|activator)s?\b")


def extract_targets(title):
    found = []
    for name, rx in _TARGET_RES:
        if rx.search(title):
            found.append(name)
    if not found:
        m = GENERIC_TARGET_RE.search(title)
        if m:
            found.append(m.group(1) + "（推测）")
    return found


def main():
    folder = sys.argv[1]
    data = json.load(open(f"{folder}/publications.json", encoding="utf-8"))
    recs = data["records"]

    for r in recs:
        r["category"] = classify(r)
        r["targets"] = (extract_targets(r.get("title", ""))
                        if r["category"] in TARGET_CATEGORIES else [])

    cat_stat = Counter(r["category"] for r in recs)
    target_stat = Counter()
    for r in recs:
        for t in r["targets"]:
            target_stat[t] += 1

    # 申请人归一化（去标点、统一大小写）
    def norm_app(a):
        a = re.sub(r"[.,]", "", a.upper())
        a = re.sub(r"\s+", " ", a).strip()
        return a

    app_stat = Counter(norm_app(r.get("applicant", "")) for r in recs if r.get("applicant"))

    analysis = {
        "publication_day": data["publication_day"],
        "total": len(recs),
        "category_stat": dict(cat_stat.most_common()),
        "target_stat": dict(target_stat.most_common()),
        "applicant_stat": dict(app_stat.most_common(40)),
        "records": recs,
    }
    with open(f"{folder}/analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    # 分组全量清单
    lines = [f"# WIPO PCT 新公开全量清单（{data['publication_day']}，A61/C07，共 {len(recs)} 件）\n"]
    by_cat = defaultdict(list)
    for r in recs:
        by_cat[r["category"]].append(r)
    for cat in CATEGORIES:
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append(f"\n## {cat}（{len(items)} 件）\n")
        if cat in COLLAPSED_CATEGORIES:
            lines.append("\n（已折叠：器械、诊断、制剂、材料等非药品/非早期研发类，"
                         "明细见 analysis.json 或 publications.csv）\n")
            continue
        by_ipc = defaultdict(list)
        for r in items:
            g = re.match(r"([A-HY]\d{2}[A-Z])", r.get("ipc_main", ""))
            by_ipc[g.group(1) if g else "其他"].append(r)
        for g, rs in sorted(by_ipc.items(), key=lambda kv: -len(kv[1])):
            lines.append(f"\n### {g}（{len(rs)}）\n")
            for r in rs:
                t = f" | 靶点: {', '.join(r['targets'])}" if r["targets"] else ""
                lines.append(f"- **{r['publication_number']}** | {r['title']} | "
                             f"{r.get('applicant','')}{t}")
    with open(f"{folder}/listing.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("类别分布:", json.dumps(analysis["category_stat"], ensure_ascii=False))
    print("识别到靶点的条目:", sum(1 for r in recs if r['targets']), "/", len(recs))
    print("靶点 TOP20:", json.dumps(dict(target_stat.most_common(20)), ensure_ascii=False))
    print("申请人 TOP15:", json.dumps(dict(app_stat.most_common(15)), ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
