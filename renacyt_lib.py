# ---------------------------------------------------------------------
#  renacyt_lib.py — parseo del ReporteInvestigadores (RENACYT/CONCYTEC)
#  y cruce con autores de Scopus por apellidos + iniciales.
#  El DNI se lee solo para deduplicar filas; NUNCA se serializa.
# ---------------------------------------------------------------------
import csv, re, unicodedata
from collections import defaultdict

VALID_LEVELS = {'Investigador Distinguido', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII'}

def deaccent(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def clean(s):
    return re.sub(r'\s+', ' ', deaccent(s or '').upper().replace('-', ' ').replace('.', ' ')).strip()

PARTICLES = {'DE', 'DEL', 'LA', 'LAS', 'LOS', 'DA', 'DI', 'DO', 'DOS', 'VAN', 'VON', 'Y', 'SAN', 'SANTA', 'MC', 'MAC'}

def surname_tokens(tokens):
    """Agrupa partículas con el apellido siguiente: DE LA CRUZ -> 'DE_LA_CRUZ'."""
    out, buf = [], []
    for t in tokens:
        if t in PARTICLES:
            buf.append(t)
        else:
            out.append(' '.join(buf + [t]))
            buf = []
    if buf:
        if out: out[-1] = out[-1] + ' ' + ' '.join(buf)
        else: out.append(' '.join(buf))
    return out


def parse_renacyt(path):
    """Devuelve lista de dicts {code, name, inst, cond, level, area} reparando filas desalineadas."""
    csv.field_size_limit(10**9)
    out = []
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.reader(f)
        hdr = next(r)
        for row in r:
            if len(row) < 12: continue
            code = row[0].strip()
            if not re.match(r'^P\d+', code): continue
            # localizar el campo Reglamento (ancla) por si la institución traía comas
            j = None
            for i in range(4, min(len(row), 10)):
                if row[i].startswith('RENACYT 2021') or row[i].startswith('RENACYT 2018'):
                    j = i; break
            if j is None: continue
            name = row[3].strip()
            inst = ','.join(row[4:j]).strip()
            cond = row[j+1].strip() if j+1 < len(row) else ''
            level = row[j+3].strip() if j+3 < len(row) else ''
            area = row[j+5].strip() if j+5 < len(row) else ''
            if level not in VALID_LEVELS: continue
            area2 = ' · '.join([a.strip() for a in area.split('|')[:2] if a.strip() and a.strip() != '-'])
            out.append({'code': code, 'name': name, 'inst': inst, 'cond': cond,
                        'level': level, 'area': area2})
    # dedup por código (el reporte puede repetir filas)
    seen, dedup = set(), []
    for p in out:
        if p['code'] in seen: continue
        seen.add(p['code']); dedup.append(p)
    return dedup


def scopus_keys(name):
    """Claves (apellido, iniciales) de un nombre Scopus 'Barboza-Meca, J.J.'."""
    if ',' in name:
        surn, given = name.split(',', 1)
    else:
        surn, given = name, ''
    surn_c = clean(surn)
    inis = ''.join(re.findall(r'[A-ZÑ]', deaccent(given).upper()))
    toks = surn_c.split(' ')
    grouped = surname_tokens(toks)
    keys = []
    full_surn = ' '.join(grouped)
    if inis:
        keys.append(('S2', full_surn, inis))          # apellidos completos + iniciales completas
        keys.append(('S2a', full_surn, inis[0]))      # apellidos completos + 1ra inicial
    if len(grouped) >= 1 and inis:
        keys.append(('S1', grouped[0], inis))         # 1er apellido + iniciales completas
        keys.append(('S1a', grouped[0], inis[0]))     # 1er apellido + 1ra inicial
    return keys


def renacyt_keys(name):
    """Claves candidatas de un nombre RENACYT 'BARBOZA MECA JOSHUAN JESUS'
    (apellidos primero, sin separador). Probamos 2 apellidos y 1 apellido."""
    toks = surname_tokens(clean(name).split(' '))
    keys = []
    if len(toks) >= 3:
        s2 = ' '.join(toks[:2]); g2 = toks[2:]
        i2 = ''.join(t[0] for t in g2 if t)
        keys.append(('S2', s2, i2)); keys.append(('S2a', s2, i2[0] if i2 else ''))
        keys.append(('S1', toks[0], i2)); keys.append(('S1a', toks[0], i2[0] if i2 else ''))
    if len(toks) >= 2:
        g1 = toks[1:]
        i1 = ''.join(t[0] for t in g1 if t)
        keys.append(('S1', toks[0], i1)); keys.append(('S1a', toks[0], i1[0] if i1 else ''))
    # dedup preservando orden
    seen, out = set(), []
    for k in keys:
        if k in seen or not k[2]: continue
        seen.add(k); out.append(k)
    return out


def match_renacyt(people, author_names):
    """people: lista de parse_renacyt. author_names: dict scopus_id -> nombre.
    Devuelve dict scopus_id -> persona RENACYT (solo matches inequívocos)."""
    idx = defaultdict(set)
    for aid, nm in author_names.items():
        for k in scopus_keys(nm):
            idx[k].add(aid)

    claims = defaultdict(list)   # aid -> [(prio, persona)]
    PRIO = {'S2': 0, 'S2a': 1, 'S1': 2, 'S1a': 3}
    for p in people:
        for k in renacyt_keys(p['name']):
            cands = idx.get(k, set())
            if len(cands) == 1:
                aid = next(iter(cands))
                claims[aid].append((PRIO[k[0]], p))
                break
            elif len(cands) > 1:
                break   # ambiguo: no arriesgar un match incorrecto

    matched = {}
    for aid, lst in claims.items():
        lst.sort(key=lambda x: x[0])
        if len(lst) == 1 or lst[0][0] < lst[1][0]:
            matched[aid] = lst[0][1]
        # empate entre dos personas RENACYT distintas -> se descarta (homónimos)
    return matched
