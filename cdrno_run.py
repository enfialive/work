#!/usr/bin/env python3
"""CDRNO batch runner — auto-detect chains, assign V-region + CDR SEQ ID NOs."""
import sys
sys.path.insert(0, '.')
from cdr_batch import *

seqs_raw = [
    'QVQLQQSGAELVRPGSSVKISCKASGYAFSSYWMNWVKQRPGQGLEWIGQIYPGDGDARYNGKFNGKATLTTDKSSSTAYMQLSSLTSEDSAVYFCTRSMGLGLDYWGQGTTLTVSS',
    'DVVMTQTPLSLPVSLGHQASISCRSSQSLVHSNGNTYLHWYLQKPGQSPKLLIYKVSNRFSGVPDRFSGSGSGTDFTLKISRVEAEDLGVYFCSQTTHVPPYTFGGGTKLEIK',
    'QVTLKESGPGILQSSQTLSLTCSFSGFSLSTSGMGVSWIRQPSGKGLEWLAHIYWDDDKRYNPSLKSRLTISKDTSRNQVFLKITSVDTADTATYYCARRAPYFDSPFAYWGQGTLVTVSA',
    'NIMMTQSPSSLAVSAGEKVTMSCKSSQSVLYSSNQKNYLAWYQQKPGQSPKLLIYWASTRESGVPDRFTGSGSGTDFTLTISSVQAEDLAVYYCHQYLSSLTFGAGTMLELK',
    'QVTLKESGPGILQSSQTLSLTCSFSGFSLSTSGMGVSWIRQPSGKGLEWLAHIYWDDDKRYNPSLKSRLTISKDTSRNQVFLKITSVDTADTATYYCARTIPTVVFDYWGQGTTLTVSS',
    'DIVMSQSPSSLAVSVGEKVTMSCKSSQSLLYSSNQKNYLAWYQQKPGQSPKLLIYWASTRESGVPDRFTGSGSGTDFTLTISSVKAEDLAVYYCQQYYSYRTFGGGTKLEIK',
    'DILMTQSPSSMSVSLGDAVSITCHASQVISSNIGWLQQKPGKSFKGLIYHGTNLEDGVPSRFSGSGSGADYSLTISSLESEDFADYYCVRYAQFPWTFGGGTKLEIK',
    'QVTLKESGPGILQSSQTLSLTCSFSGFSLSTSGMGVSWIRQPSGKGLEWLAHIYWDDDKRYNPSLKSRLTISKDTSRNQVFLRITSVDTADSATYHCARTTTTVVFDYWGQGTTLTVSS',
    'DIVMSQSPSSLAVSVGEKVTMSCKSSQSLLYSSNQKNYLAWYQQKPGQSPKLLIYWASTRESGVPDRFTGSGSGTDFTLTISSVKAEDLAVYYCQQYYSYRTFGGGTKLEIK',
    'QVTLKESGPGILQSSQTLSLTCSFSGFSLSTSGMGVSWIRQPSGKGLEWLAHIYWDDDKRYNPSLKSRLTISKDTSRNQVFLKITSVDTADTATYYCARNYAGYFDYWGQGTTLTVSS',
    'DIVMSQSPSSLAVSVGEKVTMSCKSSQSLLYSSNQKNYLAWYQQKPGQSPKLLIYWASTRDSGVPDRFTGSGSGTDFTLTISSVKAEDLAVYYCQQYYSYRTFGGGTRLEIK',
    'QVTLKESGPGILQSSQTLSLTCSFSGFSLSTSGMGVSWIRQPSGKGLEWLAHIYWDDDKHYNPSLKSRLTISKDTSRNQVFLKIPSVDTADTATYYCARTITTVVFDYWGQGTTLTVSS',
    'DIVMSQSPSSLAVSVGEKVTMSCKSSQSLLYSSNQKNYLAWYQQKPGQSPKLLIYWASTRESGVPDRFTGSGSGTDFTLTISSVKAEDLAVYYCLQYYSYRTFGGGTKLEIK',
    'DILMTQSPSSMSVSLGDTVSITCHASQDIRSNIGWLQQKPGKSFKGLIYHGTNLEDGVPSRFSGSGSGADYSLTISSLESEDFADYYCVQYAQFSWTFGGGSKLEIK',
    'QVTLKESGPGILQPSQTLSLTCSFSGFSLSTSGMGVSWIRQPSGKGLEWLAHIYWDDDKRYNPSLKSRLTISKDTSRNQVFLKITSVDTADTATYYCARMRIITTAFDYWGQGTTLTVSS',
    'DIVMTQSHKFMSTSVGDRVSITCKASQDVSPAVAWYQQKPGQSPKLLIYSASYRYTGVPDRFTGSGSGTDFTFTISSVQAEDLAVYYCQQHYSTPFTFGSGTKLEIK',
    'QVQLKQSGPGLVQPSQSLSITCTVSGFSLTTYGVHWVRQSPGKGLEWLGVIWRGGSTDYNAAFMTRLSITKDNSKSQVFFKMNSLQPDDTAVYYCARAGTTEPPFAYWGQGTLVTVSA',
    'DIVMSQSPSSLPVSVGEKVTMSCKSSQSLLYSRNQKNYLAWFQQKPGQSPKLLIYWASTGESGVPDRFTGSGSGTDFTLTISSVKAEDLAVYYCQQYYSYPYTFGGGTKLEIK',
    'QVQLQQSGAELVRPGSSVKISCKASGYEFSSYWMNWVKQRPGQGLEWIGQIYPGDGDTNYNGKFKGKATLTADKSSSKAYMQFSSLTSEDSAVYFCARSMSYSDYWGQGTTLTVSS',
    'DIVMSQSPSSLAVSVGEKANMSCKSSQSLLYTTNQKNYLAWYQQKPGQAPKLLIYWASTRESGVPDRFTGSGSGTDFTLTISSVKAEDLAIYYCQQYSSYPRTFGGGTKLEIK',
    'DVQLQESGPGLVKPSQSLSLTCTVTGYSITSDYAWNWIRQFPGNKLEWMGFISYSGGTIYNPSLKSRFSITRDTSKNLFFLQLKSVTSEDTATYYCSRNNGYGFDYWGQGTSLTVSS',
    'QIVLTQSPAIMSASPGERVTMTCSVSSSISYIHWYQQKSGTSPKRWIYDTSKLTSGVPARFSGSGSGTSYSLTISNMEAEDAATYYCQQWSTYPLTFGAGTKLELK',
    'QVQLQQPGAELVKPGASVRMSCKASGYTFSSYNMHWVKQTPGQGLDWIGSIYPGNGDTSYNQKFKGKATLTADKSSSTAYMQLSSLTSEDSAVYYCAKGDGYDRLDYWGQGTSVTVSS',
    'DIVMTQSQKFMSTSVGDRVSVTCRASQNVGTNVVWYQQKPGQSPKPLIFSASYRFSGVPDRFTGSVSGTDFTLTISNVQSEDLAEYFCQQYKSYPHTFGGGTKLEIR',
    'DVQLQESGPGLVKPSQSLSLTCTVTGYSITSDYAWNWIRQFPGNKLEWMGYISYSGYTTYNPSLKSRFSFTRDTSKNQFFLQLNSVTTEDTGTYYCATNNGYGFDYWGQGATLTVSS',
    'QIALTQSPAIMSASPGEKVTMTCSASSSVSYMHWYQQKSGTSPKRWIYDTSKLASGVPARFSGSGSGTSYSLTISSMEAEDAGTYYCQQWSTYPLTFGAGTKLELK',
    'EVKLVESGGGLVKPRGSLKLSCAASAFTFSSYAMSWVRQTPEKRLEWVASISSGGSTSYPDSVKGRFTISRDNARNILYLQMSSLRSEDTAMYYCARGSPYWYFDVWGAGTTVTVSS',
    'DIVMTQSQKFMSTSVGDRVSVTCKASQNVGISVAWYQQKSGQSPKALIYSASYRYSGVPDRFTGSGSGTDFTLTISNVQSEDLAEYFCQQYNRYPTFGGGTKLEIK',
    'DIVMTQSQKFMSTSVGDRVSVTCKASQNVGISVAWYQQKSGQSPKALIYSASYRYSGVPDRFTGSGSGTDFTLTISNVQSEDLAEYFCQQYNRDPTFGGGTKLEIK',
    'QVQLQQPGTELVKPGASVKMSCKASGYTFASYNIHWVKQTPGQGLEWIASIYPGNGDPSYNQKFKGKATLTADTSSSTAYMQLSSLTSEDSAVYYCAKGDGYDRLDYWGQGTSVTVSS',
    'DIVMTQSQKFMSTSVGDRVSVTCKASQNVGTYVVWYQQKPGQSPKPLIYSASYRFSEVPDRFTGSGSGTDFTLTISNVQSEDLAEYFCHQYNNYPHTFGGGTKLEVK',
]

schemes = ['Kabat', 'Chothia', 'IMGT', 'AbM']
chain_names = {'VH': 'Heavy', 'VK': 'Kappa', 'VL': 'Lambda'}

# Step 1: Detect chains, assign labels
detected = []
counts = {'VH': 0, 'VK': 0, 'VL': 0}
for s in seqs_raw:
    ct = detect_chain(s)
    counts[ct] += 1
    label = f'{ct}-{counts[ct]}'
    detected.append((label, ct, s))

# Step 2: SEQ ID NO for V-region sequences
vseq_to_id = {}
vseq_ids = []
next_id = 1
for label, ct, s in detected:
    if s not in vseq_to_id:
        vseq_to_id[s] = next_id
        next_id += 1
    vseq_ids.append((label, ct, s, vseq_to_id[s]))

# Step 3: Analyze all CDRs
cdr_entries = []  # (label, cdr_name, scheme, seq)
for label, ct, s in detected:
    for d in schemes:
        result = analyze_cdr(s, d)
        for reg in result['regions']:
            if reg['name'].startswith('CDR'):
                cdr_entries.append((label, reg['name'], d, reg['sequence']))

# Step 4: SEQ ID NO for CDR sequences
cdr_seq_to_id = {}
cdr_seq_ids = []
for label, cdr_name, scheme, seq in cdr_entries:
    if seq not in cdr_seq_to_id:
        cdr_seq_to_id[seq] = next_id
        next_id += 1
    cdr_seq_ids.append((label, cdr_name, scheme, seq, cdr_seq_to_id[seq]))

# ---- OUTPUT ----

# Table 0: V-region
print('## 表格0: V-region Seq NO')
print()
print('| # | Variant | Type | Length | SEQ ID NO |')
print('|---|---------|------|--------|-----------|')
for i, (label, ct, s, sid) in enumerate(vseq_ids):
    s_preview = s[:35] + '...' + s[-10:]
    print(f'| {i+1} | **{label}** | {chain_names.get(ct,ct)} | {len(s)} aa | SEQ ID NO: {sid} |')
print()

# Separate VH and VL
def chain_key(x):
    return x[1]  # ct

vh_variants = [(l, ct, s, sid) for l, ct, s, sid in vseq_ids if ct == 'VH']
vl_variants = [(l, ct, s, sid) for l, ct, s, sid in vseq_ids if ct in ('VK', 'VL')]

vh_cdrs = [(l, cn, sc, seq, sid) for l, cn, sc, seq, sid in cdr_seq_ids if cn.startswith('CDR-H')]
vl_cdrs = [(l, cn, sc, seq, sid) for l, cn, sc, seq, sid in cdr_seq_ids if cn.startswith('CDR-L')]

# Table 1A: VH CDR
print('## Table 1A: Heavy Chain CDR Annotation')
print()
header = '| Variant | CDR | Kabat | Chothia | IMGT | AbM |'
sep    = '|---------|-----|-------|---------|------|-----|'
print(header)
print(sep)

vhs = [l for l, ct, s, sid in vh_variants]
ref_vh = vhs[0]

for vi, vh_name in enumerate(vhs):
    for cdr_name in ['CDR-H1', 'CDR-H2', 'CDR-H3']:
        cells = []
        for d in schemes:
            matches = [sid for l, cn, sc, seq, sid in vh_cdrs
                       if l == vh_name and cn == cdr_name and sc == d]
            sid = matches[0] if matches else '?'
            ref_matches = [sid2 for l, cn, sc, seq, sid2 in vh_cdrs
                           if l == ref_vh and cn == cdr_name and sc == d]
            ref_sid = ref_matches[0] if ref_matches else None
            if vi > 0 and sid != ref_sid:
                cells.append(f' **SEQ ID NO: {sid}** ')
            else:
                cells.append(f' SEQ ID NO: {sid} ')
        print(f'| **{vh_name}** | {cdr_name} |{"|".join(cells)}|')

print()

# Table 1B: VL CDR
print('## Table 1B: Light Chain CDR Annotation')
print()
print(header)
print(sep)

vls = [l for l, ct, s, sid in vl_variants]
ref_vl = vls[0]

for vi, vl_name in enumerate(vls):
    for cdr_name in ['CDR-L1', 'CDR-L2', 'CDR-L3']:
        cells = []
        for d in schemes:
            matches = [sid for l, cn, sc, seq, sid in vl_cdrs
                       if l == vl_name and cn == cdr_name and sc == d]
            sid = matches[0] if matches else '?'
            ref_matches = [sid2 for l, cn, sc, seq, sid2 in vl_cdrs
                           if l == ref_vl and cn == cdr_name and sc == d]
            ref_sid = ref_matches[0] if ref_matches else None
            if vi > 0 and sid != ref_sid:
                cells.append(f' **SEQ ID NO: {sid}** ')
            else:
                cells.append(f' SEQ ID NO: {sid} ')
        print(f'| **{vl_name}** | {cdr_name} |{"|".join(cells)}|')

print()

# Table 2: SEQ ID NO sequence list
print('## Table 2: SEQ ID NO Sequence List')
print()
print('| SEQ ID NO | Type | Sequence | Length |')
print('|-----------|------|----------|--------|')

all_unique = []

# V-region entries
for seq, sid in sorted(vseq_to_id.items(), key=lambda x: x[1]):
    labels = [l for l, ct, s, sid2 in vseq_ids if s == seq]
    all_unique.append((sid, 'V-region', seq, len(seq)))

# CDR entries
for seq, sid in sorted(cdr_seq_to_id.items(), key=lambda x: x[1]):
    sources = list(set((cn,) for l, cn, sc, seq2, sid2 in cdr_seq_ids if seq2 == seq))
    cdr_name = sources[0][0] if sources else 'CDR'
    all_unique.append((sid, cdr_name, seq, len(seq)))

all_unique.sort(key=lambda x: x[0])

for sid, typ, seq, length in all_unique:
    seq_d = seq if len(seq) <= 55 else seq[:52] + '...'
    print(f'| SEQ ID NO: {sid} | {typ} | {seq_d} | {length} |')

print()
print(f'Total unique sequences: {next_id - 1}')
