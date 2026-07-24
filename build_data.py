# =====================================================================
#  Observatorio Bibliométrico del Perú — build_data.py
#  Genera data.js desde el export SciVal "Publications in Peru 1996->2026"
#  Reemplaza a build_data.R + filter_peru.py
#
#  Correcciones respecto a la versión anterior:
#   * Percentiles de CiteScore en este export están INVERTIDOS (1 = top 1%).
#     Q1 = percentil <= 25 (antes se usaba >= 75, que contaba el Q4).
#   * Serie completa 1996-2026 (2026 parcial, corte 15-jul-2026).
#   * Añade pares investigador×institución para el Top 10 institucional
#     (se excluyen publicaciones con > 100 autores, hiperautoría).
# =====================================================================
import csv, json, sys, unicodedata
from collections import Counter, defaultdict

csv.field_size_limit(10**9)

CSV_IN   = 'pubs.csv'
OUT      = 'data.js'
Y0, Y1   = 1996, 2026
NYEARS   = Y1 - Y0 + 1
MIN_PUBS_AUTHOR = 5
MIN_PUBS_INST   = 5
MIN_PUBS_PAIR   = 5
HYPER_AUTHORS   = 100   # umbral de hiperautoría para pares autor×institución

def norm(s):
    return unicodedata.normalize('NFC', s.replace('""', '"')).strip()

# ---- allow-list de instituciones peruanas -----------------------------
PERU = {norm(n) for n in json.load(open('peru_allowlist.json'))}
PERU |= {
    'University Of Huanuco',
    'Instituto de Estudios Peruanos',
    'PerúPetro S.A.',
    'Servicio Nacional de Sanidad Agraria',
    'Instituto Nacional de Oftalmología “Dr. Francisco Contreras Campos”',
}

def fnum(x):
    try:
        v = float(x)
        return v
    except (ValueError, TypeError):
        return None

def open_reader():
    f = open(CSV_IN, encoding='utf-8-sig', newline='')
    r = csv.reader(f)
    for _ in range(19):
        next(r)
    hdr = next(r)
    ix = {h: i for i, h in enumerate(hdr)}
    return f, r, ix

# =====================================================================
#  PASO 1: contar publicaciones por autor (para poda de memoria)
# =====================================================================
print('Paso 1: conteo por autor...', flush=True)
auth_count = Counter()
f, r, ix = open_reader()
IY, IIDS = ix['Year'], ix['Scopus Author Ids']
for row in r:
    if len(row) < 60: continue
    try: y = int(row[IY])
    except ValueError: continue
    if not (Y0 <= y <= Y1): continue
    ids = row[IIDS]
    if ids and ids != '-':
        for a in set(x.strip() for x in ids.split('|')):
            if a and a != '-':
                auth_count[a] += 1
f.close()
keep_auth = {a for a, c in auth_count.items() if c >= MIN_PUBS_AUTHOR}
print(f'  autores únicos: {len(auth_count):,} | con >= {MIN_PUBS_AUTHOR} pubs: {len(keep_auth):,}')
del auth_count

# =====================================================================
#  PASO 2: agregación completa
# =====================================================================
print('Paso 2: agregación...', flush=True)

def new_acc():
    return {
        'n': 0, 'cit': 0.0, 'ncit': 0, 'fw': 0.0, 'nfw': 0,
        't10': 0, 'oa': 0, 'q1': 0, 'intl': 0, 'nintl': 0,
        'y': [0]*NYEARS, 'names': Counter(), 'areas': Counter()
    }

auth = defaultdict(new_acc)
inst = defaultdict(new_acc)
pair = defaultdict(lambda: {'n':0,'cit':0.0,'ncit':0,'fw':0.0,'nfw':0,'t10':0,'q1':0,'oa':0,'intl':0,'nintl':0})

nat = new_acc()

f, r, ix = open_reader()
IY   = ix['Year']
ICIT = ix['Citations']
IFW  = ix['Field-Weighted Citation Impact']
ICS  = ix['CiteScore percentile (publication year) *']
ITP  = ix['Outputs in Top Citation Percentiles, per percentile']
INC  = ix['Number of Countries/Regions']
IOA  = ix['Open Access']
IAU  = ix['Authors']
IIDS = ix['Scopus Author Ids']
IIN  = ix['Institutions']
IAS  = ix['All Science Journal Classification (ASJC) field name']
INA  = ix['Number of Authors']

nproc = 0
for row in r:
    if len(row) < 60: continue
    try: y = int(row[IY])
    except ValueError: continue
    if not (Y0 <= y <= Y1): continue
    nproc += 1
    yi = y - Y0

    cit  = fnum(row[ICIT])
    fw   = fnum(row[IFW])
    cs   = fnum(row[ICS])
    tp   = fnum(row[ITP])
    nc   = fnum(row[INC])
    oa_r = row[IOA]

    oa   = not (oa_r is None or oa_r == '' or oa_r == '-')
    intl = None if nc is None else (nc > 1)
    t10  = tp is not None and 0 < tp <= 10
    q1   = cs is not None and 0 <= cs <= 25       # percentil invertido: 1 = mejor
    asjc = row[IAS]
    area = asjc.split('|')[0].strip() if asjc and asjc != '-' else ''
    if not area or area == '-': area = 'Sin clasificar'

    def feed(a, with_meta_label=None):
        a['n'] += 1
        a['y'][yi] += 1
        if cit is not None: a['cit'] += cit; a['ncit'] += 1
        if fw  is not None: a['fw']  += fw;  a['nfw']  += 1
        if t10: a['t10'] += 1
        if oa:  a['oa']  += 1
        if q1:  a['q1']  += 1
        if intl is not None:
            a['nintl'] += 1
            if intl: a['intl'] += 1
        a['areas'][area] += 1

    feed(nat)

    # ---- instituciones (solo Perú) ----
    peru_insts = []
    insts_r = row[IIN]
    if insts_r and insts_r != '-':
        for v in set(norm(x) for x in insts_r.split('|')):
            if v and v != '-' and v in PERU:
                peru_insts.append(v)
                a = inst[v]
                feed(a)
                a['names'][v] += 1

    # ---- autores ----
    ids_r, au_r = row[IIDS], row[IAU]
    paper_auth = []
    if ids_r and ids_r != '-':
        idl = [x.strip() for x in ids_r.split('|')]
        nml = [x.strip() for x in au_r.split('|')] if au_r else []
        k = min(len(idl), len(nml)) if nml else len(idl)
        seen = set()
        for j in range(k):
            aid = idl[j]
            if not aid or aid == '-' or aid in seen: continue
            seen.add(aid)
            if aid in keep_auth:
                paper_auth.append(aid)
                a = auth[aid]
                feed(a)
                a['names'][nml[j] if j < len(nml) else aid] += 1

    # ---- pares autor×institución (sin hiperautoría) ----
    try: nauth = int(row[INA])
    except ValueError: nauth = len(paper_auth)
    if nauth <= HYPER_AUTHORS and peru_insts and paper_auth:
        for iv in peru_insts:
            for aid in paper_auth:
                p = pair[(iv, aid)]
                p['n'] += 1
                if cit is not None: p['cit'] += cit; p['ncit'] += 1
                if fw  is not None: p['fw']  += fw;  p['nfw']  += 1
                if t10: p['t10'] += 1
                if q1:  p['q1']  += 1
                if oa:  p['oa']  += 1
                if intl is not None:
                    p['nintl'] += 1
                    if intl: p['intl'] += 1
f.close()
print(f'  publicaciones procesadas ({Y0}-{Y1}): {nproc:,}')
print(f'  autores agregados: {len(auth):,} | instituciones Perú: {len(inst):,} | pares: {len(pair):,}')

# =====================================================================
#  PASO 3: serialización
# =====================================================================
print('Paso 3: serialización...', flush=True)

def pct(k, n): return round(k / n * 100, 1) if n else 0
def finish(key, a):
    return {
        'id': key,
        'name': a['names'].most_common(1)[0][0] if a['names'] else key,
        'n_pubs': a['n'],
        'cit_total': round(a['cit']),
        'cit_mean': round(a['cit'] / a['ncit'], 1) if a['ncit'] else 0,
        'fwci_mean': round(a['fw'] / a['nfw'], 2) if a['nfw'] else 0,
        'pct_top10': pct(a['t10'], a['n']),
        'pct_oa':   pct(a['oa'],  a['n']),
        'pct_intl': pct(a['intl'], a['nintl']),
        'pct_q1':   pct(a['q1'],  a['n']),
        'y': a['y'],
        'areas': '; '.join(x for x, _ in a['areas'].most_common(4)),
    }

res = sorted((finish(k, a) for k, a in auth.items() if a['n'] >= MIN_PUBS_AUTHOR),
             key=lambda d: -d['n_pubs'])
ins = sorted((finish(k, a) for k, a in inst.items() if a['n'] >= MIN_PUBS_INST),
             key=lambda d: -d['n_pubs'])
print(f'  investigadores (>= {MIN_PUBS_AUTHOR}): {len(res):,} | instituciones (>= {MIN_PUBS_INST}): {len(ins):,}')

nat_out = {
    'total_pubs': nat['n'],
    'cit_mean':  round(nat['cit'] / nat['ncit'], 2) if nat['ncit'] else 0,
    'fwci_mean': round(nat['fw'] / nat['nfw'], 2) if nat['nfw'] else 0,
    'pct_oa':   pct(nat['oa'], nat['n']),
    'pct_intl': pct(nat['intl'], nat['nintl']),
    'pct_top10': pct(nat['t10'], nat['n']),
    'pct_q1':   pct(nat['q1'], nat['n']),
    'by_year':  nat['y'],
    'y0': Y0, 'y1': Y1,
    'data_date': '15 de julio de 2026',
    'export_date': '24 de julio de 2026',
}
print('  NACIONAL:', {k: v for k, v in nat_out.items() if k != 'by_year'})

# Top investigadores por institución: pares con >= MIN_PUBS_PAIR pubs
res_ids = {d['id'] for d in res}
inst_top = defaultdict(list)
for (iv, aid), p in pair.items():
    if p['n'] < MIN_PUBS_PAIR or aid not in res_ids: continue
    inst_top[iv].append([
        aid, p['n'], round(p['cit']),
        round(p['cit'] / p['ncit'], 1) if p['ncit'] else 0,
        round(p['fw'] / p['nfw'], 2) if p['nfw'] else 0,
        pct(p['t10'], p['n']),
        pct(p['q1'],  p['n']),
        pct(p['oa'],  p['n']),
        pct(p['intl'], p['nintl']),
    ])
for iv in inst_top:
    inst_top[iv].sort(key=lambda x: -x[1])
npairs = sum(len(v) for v in inst_top.values())
print(f'  pares serializados (>= {MIN_PUBS_PAIR} pubs con la institución): {npairs:,} en {len(inst_top)} instituciones')

def js_dump(o):
    return json.dumps(o, ensure_ascii=False, separators=(',', ':'))

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('// Datos generados con build_data.py — Fuente: Scopus/SciVal\n')
    f.write('// Datos al 15 de julio de 2026 · export del 24 de julio de 2026 · serie 1996–2026 (2026 parcial)\n')
    f.write('// Instituciones: solo entidades con sede en el Perú (allow-list curada).\n')
    f.write('// Q1 = percentil CiteScore <= 25 (percentil invertido en el export: 1 = top 1%).\n')
    f.write('window.NATIONAL = ' + js_dump(nat_out) + ';\n')
    f.write('window.RESEARCHERS = ' + js_dump(res) + ';\n')
    f.write('window.INSTITUTIONS = ' + js_dump(ins) + ';\n')
    f.write('// INST_TOP[institución] = [[authorId, n_pubs, cit_total, cit_mean, fwci_mean, pct_top10, pct_q1, pct_oa, pct_intl], ...]\n')
    f.write('window.INST_TOP = ' + js_dump(dict(inst_top)) + ';\n')

import os
print(f'data.js generado: {os.path.getsize(OUT)/1e6:.2f} MB')
print('Listo.')
