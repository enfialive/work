#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CDR 批量标注工具 — 一次性输出多种定义方案下的 CDR 序列罗列

用法：
  python cdr_batch.py "QVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKDYGDYWGQGTLVTVSS"

  或交互式：
  python cdr_batch.py
  然后粘贴序列

支持的定义方案：Kabat, Chothia, IMGT, AbM
"""

import sys
import math

# ==================== BLOSUM62 ====================

AA_ORDER = 'ARNDCQEGHILKMFPSTWYV'
BLOSUM62_MATRIX = [
    [ 4,-1,-2,-2, 0,-1,-1, 0,-2,-1,-1,-1,-1,-2,-1, 1, 0,-3,-2, 0],
    [-1, 5, 0,-2,-3, 1, 0,-2, 0,-3,-2, 2,-1,-3,-2,-1,-1,-3,-2,-3],
    [-2, 0, 6, 1,-3, 0, 0, 0, 1,-3,-3, 0,-2,-3,-2, 1, 0,-4,-2,-3],
    [-2,-2, 1, 6,-3, 0, 2,-1,-1,-3,-4,-1,-3,-3,-1, 0,-1,-4,-3,-3],
    [ 0,-3,-3,-3, 9,-3,-4,-3,-3,-1,-1,-3,-1,-2,-3,-1,-1,-2,-2,-1],
    [-1, 1, 0, 0,-3, 5, 2,-2, 0,-3,-2, 1, 0,-3,-1, 0,-1,-2,-1,-2],
    [-1, 0, 0, 2,-4, 2, 5,-2, 0,-3,-3, 1,-2,-3,-1, 0,-1,-3,-2,-2],
    [ 0,-2, 0,-1,-3,-2,-2, 6,-2,-4,-4,-2,-3,-3,-2, 0,-2,-2,-3,-3],
    [-2, 0, 1,-1,-3, 0, 0,-2, 8,-3,-3,-1,-2,-1,-2,-1,-2,-2, 2,-3],
    [-1,-3,-3,-3,-1,-3,-3,-4,-3, 4, 2,-3, 1, 0,-3,-2,-1,-3,-1, 3],
    [-1,-2,-3,-4,-1,-2,-3,-4,-3, 2, 4,-2, 2, 0,-3,-2,-1,-2,-1, 1],
    [-1, 2, 0,-1,-3, 1, 1,-2,-1,-3,-2, 5,-1,-3,-1, 0,-1,-3,-2,-2],
    [-1,-1,-2,-3,-1, 0,-2,-3,-2, 1, 2,-1, 5, 0,-2,-1,-1,-1,-1, 1],
    [-2,-3,-3,-3,-2,-3,-3,-3,-1, 0, 0,-3, 0, 6,-4,-2,-2, 1, 3,-1],
    [-1,-2,-2,-1,-3,-1,-1,-2,-2,-3,-3,-1,-2,-4, 7,-1,-1,-4,-3,-2],
    [ 1,-1, 1, 0,-1, 0, 0, 0,-1,-2,-2, 0,-1,-2,-1, 4, 1,-3,-2,-2],
    [ 0,-1, 0,-1,-1,-1,-1,-2,-2,-1,-1,-1,-1,-2,-1, 1, 5,-2,-2, 0],
    [-3,-3,-4,-4,-2,-2,-3,-2,-2,-3,-2,-3,-1, 1,-4,-3,-2,11, 2,-3],
    [-2,-2,-2,-3,-2,-1,-2,-3, 2,-1,-1,-2,-1, 3,-3,-2,-2, 2, 7,-1],
    [ 0,-3,-3,-3,-1,-2,-2,-3,-3, 3, 1,-2, 1,-1,-2,-2, 0,-3,-1, 4],
]

# 建立双向查找字典
BLOSUM62 = {}
for i, a in enumerate(AA_ORDER):
    for j, b in enumerate(AA_ORDER):
        BLOSUM62[a + b] = BLOSUM62_MATRIX[i][j]


def blosum(a, b):
    key = a + b
    if key in BLOSUM62:
        return BLOSUM62[key]
    return BLOSUM62.get(b + a, -4)


# ==================== 参考序列 ====================
# 每个参考序列含: seq, kabat编号数组, imgt编号数组, chain标识, 插入位置定义

def make_kabat_vh():
    """VH Kabat主编号 (不含插入位)"""
    p = []
    for i in range(1, 36): p.append(i)       # 1-35
    for i in range(36, 53): p.append(i)      # 36-52
    for i in range(53, 66): p.append(i)      # 53-65 (跳过52A-E)
    for i in range(66, 83): p.append(i)      # 66-82
    for i in range(83, 95): p.append(i)      # 83-94 (跳过82A-C)
    for i in range(95, 101): p.append(i)     # 95-100
    for i in range(101, 114): p.append(i)    # 101-113 (跳过100A-K)
    return p


def make_imgt_vh():
    p = []
    for i in range(1, 27): p.append(i)       # FR1: 1-26
    for i in range(27, 39): p.append(i)      # CDR1: 27-38
    for i in range(39, 56): p.append(i)      # FR2: 39-55
    for i in range(56, 66): p.append(i)      # CDR2: 56-65
    for i in range(66, 105): p.append(i)     # FR3: 66-104
    for i in range(105, 118): p.append(i)    # CDR3: 105-117
    for i in range(118, 129): p.append(i)    # FR4: 118-128
    return p


def make_kabat_vk():
    p = []
    for i in range(1, 24): p.append(i)
    for i in range(24, 35): p.append(i)
    for i in range(35, 50): p.append(i)
    for i in range(50, 57): p.append(i)
    for i in range(57, 89): p.append(i)
    for i in range(89, 98): p.append(i)
    for i in range(98, 108): p.append(i)
    return p


def make_imgt_vk():
    p = []
    for i in range(1, 27): p.append(i)
    for i in range(27, 39): p.append(i)
    for i in range(39, 56): p.append(i)
    for i in range(56, 66): p.append(i)
    for i in range(66, 105): p.append(i)
    for i in range(105, 118): p.append(i)
    for i in range(118, 128): p.append(i)
    return p


def make_kabat_vl():
    p = []
    for i in range(1, 24): p.append(i)
    for i in range(24, 35): p.append(i)
    for i in range(35, 50): p.append(i)
    for i in range(50, 57): p.append(i)
    for i in range(57, 89): p.append(i)
    for i in range(89, 98): p.append(i)
    for i in range(98, 107): p.append(i)
    return p


REF = {
    'VH': {
        'seq': 'EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAKGGYFDYWGQGTLVTV',
        'kabat': make_kabat_vh(),
        'imgt': make_imgt_vh(),
        'chain': 'H',
        'insertions': {
            35: [35.1, 35.2],
            52: [52.1, 52.2, 52.3, 52.4, 52.5],
            82: [82.1, 82.2, 82.3],
            100: [100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7, 100.8, 100.9, 100.10, 100.11]
        }
    },
    'VK': {
        'seq': 'DIQMTQSPSSLSASVGDRVTITCRASQSISSYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQSYSTPLTFGGGTKVEIK',
        'kabat': make_kabat_vk(),
        'imgt': make_imgt_vk(),
        'chain': 'L',
        'insertions': {
            27: [27.1, 27.2, 27.3, 27.4, 27.5, 27.6],
            95: [95.1, 95.2, 95.3, 95.4, 95.5, 95.6]
        }
    },
    'VL': {
        'seq': 'QSVLTQPPSASGTPGQRVTISCSGSSSNIGSNYVYWYQQLPGTAPKLLIYRNNQRPSGVPDRFSGSKSGTSASLAISGLRSEDEADYYCAAWDDSLSGPVFGGGTK',
        'kabat': make_kabat_vl(),
        'imgt': make_imgt_vk(),
        'chain': 'L',
        'insertions': {
            27: [27.1, 27.2, 27.3, 27.4, 27.5, 27.6],
            95: [95.1, 95.2, 95.3, 95.4, 95.5, 95.6]
        }
    }
}


# ==================== CDR定义方案边界 (基于Kabat编号) ====================

CDR_DEFS = {
    'Kabat': {
        'H': [
            ('FR1', 1, 30),
            ('CDR-H1', 31, 35.9),
            ('FR2', 36, 49),
            ('CDR-H2', 50, 65.9),
            ('FR3', 66, 94),
            ('CDR-H3', 95, 102.9),
            ('FR4', 103, 113),
        ],
        'L': [
            ('FR1', 1, 23),
            ('CDR-L1', 24, 34.9),
            ('FR2', 35, 49),
            ('CDR-L2', 50, 56.9),
            ('FR3', 57, 88),
            ('CDR-L3', 89, 97.9),
            ('FR4', 98, 107),
        ]
    },
    'Chothia': {
        'H': [
            ('FR1', 1, 25),
            ('CDR-H1', 26, 32.9),
            ('FR2', 33, 51),
            ('CDR-H2', 52, 56.9),
            ('FR3', 57, 94),
            ('CDR-H3', 95, 102.9),
            ('FR4', 103, 113),
        ],
        'L': [
            ('FR1', 1, 23),
            ('CDR-L1', 24, 34.9),
            ('FR2', 35, 49),
            ('CDR-L2', 50, 56.9),
            ('FR3', 57, 88),
            ('CDR-L3', 89, 97.9),
            ('FR4', 98, 107),
        ]
    },
    'IMGT': {
        'H': [
            ('FR1', 1, 25),
            ('CDR-H1', 26, 33.9),
            ('FR2', 34, 50),
            ('CDR-H2', 51, 57.9),
            ('FR3', 58, 92),
            ('CDR-H3', 93, 102.9),
            ('FR4', 103, 113),
        ],
        'L': [
            ('FR1', 1, 26),
            ('CDR-L1', 27, 32.9),
            ('FR2', 33, 49),
            ('CDR-L2', 50, 52.9),
            ('FR3', 53, 88),
            ('CDR-L3', 89, 97.9),
            ('FR4', 98, 107),
        ]
    },
    'AbM': {
        'H': [
            ('FR1', 1, 25),
            ('CDR-H1', 26, 35.9),
            ('FR2', 36, 49),
            ('CDR-H2', 50, 58.9),
            ('FR3', 59, 94),
            ('CDR-H3', 95, 102.9),
            ('FR4', 103, 113),
        ],
        'L': [
            ('FR1', 1, 23),
            ('CDR-L1', 24, 34.9),
            ('FR2', 35, 49),
            ('CDR-L2', 50, 56.9),
            ('FR3', 57, 88),
            ('CDR-L3', 89, 97.9),
            ('FR4', 98, 107),
        ]
    }
}


# ==================== NW 全局比对 ====================

def nw_align(seq1, seq2, gap_penalty=8):
    """Needleman-Wunsch 全局比对, 返回 (比对后seq1, 比对后seq2, 得分)"""
    n, m = len(seq1), len(seq2)
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    trace = [[0] * (m + 1) for _ in range(n + 1)]  # 0=diag, 1=up, 2=left

    for i in range(n + 1):
        dp[i][0] = -i * gap_penalty
        trace[i][0] = 1
    for j in range(m + 1):
        dp[0][j] = -j * gap_penalty
        trace[0][j] = 2
    trace[0][0] = 0

    for i in range(1, n + 1):
        a1 = seq1[i - 1]
        for j in range(1, m + 1):
            a2 = seq2[j - 1]
            diag = dp[i - 1][j - 1] + blosum(a1, a2)
            up = dp[i - 1][j] - gap_penalty
            left = dp[i][j - 1] - gap_penalty
            if diag >= up and diag >= left:
                dp[i][j] = diag
                trace[i][j] = 0
            elif up >= left:
                dp[i][j] = up
                trace[i][j] = 1
            else:
                dp[i][j] = left
                trace[i][j] = 2

    # 回溯
    i, j = n, m
    aln1, aln2 = [], []
    while i > 0 or j > 0:
        t = trace[i][j]
        if t == 0:
            aln1.append(seq1[i - 1])
            aln2.append(seq2[j - 1])
            i -= 1
            j -= 1
        elif t == 1:
            aln1.append(seq1[i - 1])
            aln2.append('-')
            i -= 1
        else:
            aln1.append('-')
            aln2.append(seq2[j - 1])
            j -= 1
    aln1.reverse()
    aln2.reverse()
    return ''.join(aln1), ''.join(aln2), dp[n][m]


# ==================== 链类型检测 ====================

def detect_chain(seq):
    s = seq.upper()
    import re
    vh_fr4 = bool(re.search(r'WG.QG', s))
    vk_fr4 = bool(re.search(r'FG.GTK', s))
    vl_fr4 = bool(re.search(r'FG.GT[KL]', s))
    vh_n = bool(re.search(r'^[EQ]V[QK]L', s))
    vk_n = bool(re.search(r'^[DE]IQM', s))
    vl_n = bool(re.search(r'^[QS][SV]L', s))

    if vh_fr4 and vh_n:
        return 'VH'
    if vh_fr4:
        return 'VH'
    if vk_fr4 or vk_n:
        return 'VK'
    if vl_fr4 or vl_n:
        return 'VL'

    # 回退比对
    ss = s[:min(len(s), 30)]
    best, best_sc = None, float('-inf')
    for k, v in REF.items():
        rs = v['seq'][:30]
        sc = 0
        for i in range(min(len(ss), len(rs))):
            if ss[i] == rs[i]:
                sc += 5
            else:
                sc += blosum(ss[i] if i < len(ss) else 'X',
                             rs[i] if i < len(rs) else 'X')
        if sc > best_sc:
            best_sc = sc
            best = k
    return best or 'VH'


# ==================== Kabat编号转移 ====================

def transfer_numbering(query_aln, ref_aln, ref):
    """将参考序列的Kabat编号转移到查询序列"""
    result = []
    ref_idx = 0
    last_kabat = 0
    ins_tracker = {int(k): 0 for k in ref.get('insertions', {})}

    for i in range(len(query_aln)):
        q_res = query_aln[i]
        r_res = ref_aln[i]

        if q_res != '-':
            if r_res != '-' and ref_idx < len(ref['kabat']):
                kb = ref['kabat'][ref_idx]
                im = ref['imgt'][ref_idx] if ref_idx < len(ref['imgt']) else None
                result.append({
                    'residue': q_res,
                    'kabat': kb,
                    'imgt': im,
                    'is_insertion': False,
                })
                last_kabat = kb
                base_kb = int(math.floor(kb))
                if base_kb in ins_tracker:
                    ins_tracker[base_kb] = 0
                ref_idx += 1
            else:
                # 插入残基
                base_kb = int(math.floor(last_kabat))
                insertions = ref.get('insertions', {}).get(base_kb, [])
                idx = ins_tracker.get(base_kb, 0)
                if insertions and idx < len(insertions):
                    ins_num = insertions[idx]
                else:
                    ins_num = base_kb + (idx + 1) * 0.1
                ins_tracker[base_kb] = idx + 1
                result.append({
                    'residue': q_res,
                    'kabat': ins_num,
                    'imgt': None,
                    'is_insertion': True,
                })
                last_kabat = ins_num
        else:
            if r_res != '-':
                ref_idx += 1
    return result


# ==================== 格式化 ====================

def kabat_label(num):
    """Kabat编号格式化: 35.1→35A, 35.2→35B"""
    base = int(math.floor(num))
    frac = num - base
    if frac < 0.01:
        return str(base)
    idx = round(frac * 10)
    return f"{base}{chr(64 + idx)}"


def extract_regions(numbering, chain, definition_scheme):
    """从带编号的残基列表中提取CDR/FR区域"""
    defs = CDR_DEFS.get(definition_scheme)
    if not defs:
        return []
    chain_defs = defs.get(chain)
    if not chain_defs:
        return []

    regions = []
    for name, start, end in chain_defs:
        residues = []
        for entry in numbering:
            kn = entry['kabat']
            kn_base = int(math.floor(kn))
            start_base = int(math.floor(start))
            end_base = int(math.floor(end))
            if ((kn_base > start_base and kn_base < end_base) or
                (kn_base == start_base and kn >= start) or
                (kn_base == end_base and kn <= end)):
                residues.append(entry)
        if residues:
            regions.append({
                'name': name,
                'sequence': ''.join(e['residue'] for e in residues),
                'length': len(residues),
                'start_label': kabat_label(residues[0]['kabat']),
                'end_label': kabat_label(residues[-1]['kabat']),
            })
    return regions


# ==================== 分析一条序列 ====================

def analyze_cdr(seq, defscheme):
    """分析序列，返回指定定义方案下的区域"""
    s = seq.upper()
    chain_type = detect_chain(s)
    ref = REF.get(chain_type, REF['VH'])
    chain = ref['chain']

    aln1, aln2, score = nw_align(s, ref['seq'], 8)
    numbering = transfer_numbering(aln1, aln2, ref)
    regions = extract_regions(numbering, chain, defscheme)

    return {
        'chain_type': chain_type,
        'chain': chain,
        'regions': regions,
        'numbering': numbering,
        'score': score,
        'seq_len': len(s),
    }


# ==================== 主输出 ====================

CHAIN_NAMES = {
    'VH': 'Heavy Chain (VH)',
    'VK': 'Kappa Light Chain (VK)',
    'VL': 'Lambda Light Chain (VL)',
}

# 定义方案 × 兼容的编号方案
SCHEME_COMBOS = [
    ('Kabat',   'Kabat'),
    ('Chothia', 'Chothia'),
    ('IMGT',    'IMGT'),
    ('AbM',     'AbM'),
]


def print_all_schemes(seq):
    """打印所有CDR定义方案下的结果"""
    s = seq.upper().replace('\n', '').replace(' ', '')
    # 过滤非氨基酸字符
    s = ''.join(c for c in s if c in 'ACDEFGHIKLMNPQRSTVWY')

    if len(s) < 30:
        print("ERROR: Sequence too short (<30 aa), may not be a complete V-region.")
        return

    chain_type = detect_chain(s)
    print(f"\n{'='*70}")
    print(f"  Antibody V-region CDR Multi-Scheme Annotation")
    print(f"{'='*70}")
    print(f"  Chain: {CHAIN_NAMES.get(chain_type, chain_type)}")
    print(f"  Length: {len(s)} aa")
    print(f"  Sequence: {s[:60]}{'...' if len(s) > 60 else ''}")
    print(f"{'='*70}\n")

    all_results = {}
    for def_name, num_name in SCHEME_COMBOS:
        result = analyze_cdr(s, def_name)
        all_results[def_name] = result
        chain = result['chain']

        print(f"-- {def_name} Definition Scheme (Numbering: {num_name}) {'-'*20}")
        print(f"   Alignment Score: {result['score']:.0f}")
        print(f"   {'Region':<12} {'Sequence':<30} {'Position':<14} {'Len'}")
        print(f"   {'-'*10} {'-'*30} {'-'*12} {'-'*5}")

        for r in result['regions']:
            is_cdr = r['name'].startswith('CDR')
            marker = '[CDR]' if is_cdr else '[FR] '
            seq_display = r['sequence'] if len(r['sequence']) <= 28 else r['sequence'][:25] + '...'
            pos_display = f"{r['start_label']}~{r['end_label']}"
            print(f"   {marker} {r['name']:<7} {seq_display:<30} {pos_display:<12} {r['length']:>3}")

        print()

    # ===== CDR Summary =====
    print(f"{'='*70}")
    print(f"  CDR Sequence Summary Across All Schemes")
    print(f"{'='*70}")

    # Determine max CDR count across schemes
    max_cdrs = 0
    for def_name in SCHEME_COMBOS:
        cdrs = [r for r in all_results[def_name[0]]['regions'] if r['name'].startswith('CDR')]
        max_cdrs = max(max_cdrs, len(cdrs))

    print(f"\n   {'Scheme':<10}", end='')
    for i in range(1, max_cdrs + 1):
        print(f" {'CDR-' + str(i):<28}", end='')
    print()

    print(f"   {'-'*10}", end='')
    for _ in range(max_cdrs):
        print(f" {'-'*28}", end='')
    print()

    for def_name, _ in SCHEME_COMBOS:
        cdrs = [r for r in all_results[def_name]['regions'] if r['name'].startswith('CDR')]
        print(f"   {def_name:<10}", end='')
        for cdr in cdrs:
            seq_d = cdr['sequence'] if len(cdr['sequence']) <= 26 else cdr['sequence'][:23] + '...'
            print(f" {seq_d:<28}", end='')
        print()

    print(f"\n   {'='*70}")
    print(f"   This tool uses reference-sequence alignment. Results are for")
    print(f"   research reference only. Cross-validate with abYsis / ANARCI.")
    print(f"{'='*70}\n")


def main():
    if len(sys.argv) > 1:
        seq = sys.argv[1]
        print_all_schemes(seq)
    else:
        print("Paste antibody V-region amino acid sequence (single-letter, non-FASTA):")
        print("(End input with Ctrl+Z then Enter, or Ctrl+D)")
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        seq = ''.join(lines)
        if seq.strip():
            print_all_schemes(seq)
        else:
            print("No sequence input. Usage: python cdr_batch.py <sequence>")


if __name__ == '__main__':
    main()
