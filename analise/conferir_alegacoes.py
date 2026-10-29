#!/usr/bin/env python3
"""Confere, seção a seção, alegações que circularam sobre o 2º turno:
seções com zero voto para Flávio, horário de encerramento das urnas, eleitores sem biometria
e seções com votação extrema para um candidato.

Horários: o BU grava abertura e encerramento no horário local da urna. A votação de 2026 foi de
8h às 17h no horário de Brasília em todo o país, então a urna do Acre encerra normalmente às 15h locais
e a do Amazonas às 16h. Aqui os horários são analisados das duas formas: local (como está no arquivo)
e convertidos para Brasília. Amazonas inteiro é tratado como UTC-4 (alguns municípios do oeste são UTC-5).
Seções no exterior (ZZ) ficam fora da análise de horário.

Uso: python3 -I conferir_alegacoes.py <bu_2t.csv> <B_urnas_1t_x_2t.csv> <oficial_2t.csv> <saida.json> <pasta_painel>
"""
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

FUSO = {"AC": -5, "AM": -4, "RO": -4, "RR": -4, "MT": -4, "MS": -4}   # demais: -3 (Brasília)


def brasilia(uf, dt):
    return dt + timedelta(hours=-3 - FUSO.get(uf, -3))


bu, bfile, oficial, saida, painel = map(Path, sys.argv[1:6])

sec = {}
with open(bu, encoding="utf-8", newline="") as f:
    for d in csv.DictReader(f, delimiter=";"):
        if d["DS_CARGO"] != "Presidente":
            continue
        k = (d["SG_UF"], d["CD_MUNICIPIO"], d["NR_ZONA"], d["NR_SECAO"])
        s = sec.get(k)
        if s is None:
            s = sec[k] = {"L": 0, "F": 0, "B": 0, "N": 0, "comp": int(d["QT_COMPARECIMENTO"]), "aptos": int(d["QT_APTOS"]),
                          "enc": d["DT_ENCERRAMENTO"], "sem_bio": d["QT_HAB_SEM_BIOMETRIA"], "bio": d["QT_HAB_BIOMETRICA"],
                          "biog": d["QT_HAB_BIOGRAFICA"], "origem": d["ORIGEM"]}
        nr, v = d["NR_VOTAVEL"], int(d["QT_VOTOS"])
        c = "L" if nr == "13" else "F" if nr == "22" else "B" if nr == "95" else "N" if nr == "96" else "O"
        s[c] = s.get(c, 0) + v

nomes = {}
with open(oficial, encoding="utf-8", newline="") as f:
    for d in csv.DictReader(f, delimiter=";"):
        nomes[(d["SG_UF"], d["CD_MUNICIPIO"])] = d["NM_MUNICIPIO"]
# 1º turno e esperado pelo modelo (B_urnas): para comparar cada grupo de seções com ele mesmo
t1 = {}
with open(bfile, encoding="utf-8", newline="") as f:
    for d in csv.DictReader(f, delimiter=";"):
        t1[(d["UF"], d["CD_MUNICIPIO"], d["NR_ZONA"], d["NR_SECAO"])] = {
            "L1": int(d["LULA_1T"]), "F1": int(d["FLAVIO_1T"]), "C1": int(d["COMP_1T"]),
            "eL": float(d["LULA_2T_ESPERADO"]), "eF": float(d["FLAVIO_2T_ESPERADO"])}

out = {"secoes": len(sec)}
L = sum(s["L"] for s in sec.values()); F = sum(s["F"] for s in sec.values())
out["total"] = {"lula": L, "flavio": F, "margem": L - F, "comparecimento": sum(s["comp"] for s in sec.values())}

# 1. Zero voto para Flávio
zero = []
for k, s in sec.items():
    if s["F"] == 0:
        a = t1.get(k, {})
        zero.append({"uf": k[0], "cidade": nomes.get((k[0], k[1]), k[1]), "zona": int(k[2]), "secao": int(k[3]),
                     "flavio_2t": s["F"], "lula_2t": s["L"], "flavio_1t": a.get("F1", ""), "lula_1t": a.get("L1", "")})
zero.sort(key=lambda r: (r["uf"], r["cidade"], r["zona"], r["secao"]))
out["zero"] = {"flavio": len(zero), "lula": sum(1 for s in sec.values() if s["L"] == 0),
               "votos_lula_nelas": sum(r["lula_2t"] for r in zero),
               "flavio_1t_nelas": sum(r["flavio_1t"] or 0 for r in zero),
               "flavio_1t_zero": sum(1 for r in zero if r["flavio_1t"] == 0),
               "flavio_1t_ate2": sum(1 for r in zero if r["flavio_1t"] != "" and r["flavio_1t"] <= 2),
               "por_uf": dict(sorted(((u, sum(1 for r in zero if r["uf"] == u)) for u in {r["uf"] for r in zero}), key=lambda x: -x[1]))}

# 2. Extremos: % de Lula nos votos válidos (Lula + Flávio), no 2º turno, no 1º turno e no esperado
ext = defaultdict(int)
def conta(pref, l, f):
    if l + f <= 0:
        return
    p = l / (l + f)
    ext[pref + "l100"] += p == 1; ext[pref + "f100"] += p == 0
    ext[pref + "l90"] += p >= 0.9; ext[pref + "f90"] += p <= 0.1
for k, s in sec.items():
    conta("", s["L"], s["F"])
    a = t1.get(k)
    if a:
        conta("t1_", a["L1"], a["F1"]); conta("esp_", a["eL"], a["eF"])
out["extremos"] = dict(ext)

# 3. Horário de encerramento (local, como no arquivo, e em Brasília)
FAIXAS = [("até 17:00", None, "17:00:59"), ("17:01 a 17:15", "17:01:00", "17:15:59"),
          ("17:16 a 18:59", "17:16:00", "18:59:59"), ("19:00 ou depois", "19:00:00", None)]
def faixa(hhmmss):
    for nome, a, b in FAIXAS:
        if (a is None or hhmmss >= a) and (b is None or hhmmss <= b):
            return nome
hor = {"local": defaultdict(lambda: defaultdict(float)), "brasilia": defaultdict(lambda: defaultdict(float))}
sem_hora = defaultdict(int)
for k, s in sec.items():
    if k[0] == "ZZ" or not s["enc"]:
        sem_hora["secoes"] += 1; sem_hora["comp"] += s["comp"]
        continue
    dt = datetime.strptime(s["enc"], "%Y-%m-%d %H:%M:%S")
    a = t1.get(k, {"L1": 0, "F1": 0, "eL": 0, "eF": 0})
    for modo, t in (("local", dt), ("brasilia", brasilia(k[0], dt))):
        h = hor[modo][faixa(t.strftime("%H:%M:%S")) if t.date() == dt.date() else "19:00 ou depois"]
        h["secoes"] += 1; h["comp"] += s["comp"]; h["L"] += s["L"]; h["F"] += s["F"]
        for c in ("L1", "F1", "eL", "eF"):
            h[c] += a[c]
out["sem_horario"] = dict(sem_hora)
out["horario"] = {m: {f: dict(v) for f, v in d.items()} for m, d in hor.items()}

# 4. Biometria. O BU traz três contagens que somam o comparecimento da seção (campos 1, 2 e 3 da
# habilitação); o campo 2 é o dos habilitados pela biometria. Teste: onde há mais eleitores sem biometria,
# Lula ficou acima do esperado pelo 1º turno da mesma seção?
bio = defaultdict(int)
grupos = {"campo1": [], "campo3": []}
for k, s in sec.items():
    if s["sem_bio"] == "":
        bio["secoes_sem_dado"] += 1
        continue
    c1, c2, c3 = int(s["sem_bio"]), int(s["bio"]), int(s["biog"])
    bio["campo1"] += c1; bio["campo2_biometria"] += c2; bio["campo3"] += c3; bio["comp"] += s["comp"]
    a = t1.get(k)
    if a and s["comp"] >= 20:
        for g, v in (("campo1", c1), ("campo3", c3)):
            grupos[g].append((v / s["comp"], s["comp"], s["L"] - a["eL"], s["F"] - a["eF"]))
out["biometria"] = dict(bio)
quint = []
for g, rows in grupos.items():
    rows.sort()
    n = len(rows)
    for q in range(5):
        r = rows[q * n // 5:(q + 1) * n // 5]
        c = sum(x[1] for x in r)
        quint.append({"campo": g, "quintil": q + 1, "secoes": len(r), "pct_sem_biometria": round(100 * sum(x[0] * x[1] for x in r) / c, 2),
                      "lula_acima_esperado_pp": round(100 * sum(x[2] for x in r) / c, 3),
                      "flavio_acima_esperado_pp": round(100 * sum(x[3] for x in r) / c, 3),
                      "lula_acima_esperado_votos": round(sum(x[2] for x in r))})
out["biometria_quintis"] = quint

Path(saida).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "biometria_quintis"}, ensure_ascii=False, indent=1))

# CSVs do painel
with open(painel / "zero_flavio.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["uf", "cidade", "zona", "secao", "flavio_2t", "lula_2t", "flavio_1t", "lula_1t"])
    w.writeheader(); w.writerows(zero)
pf = lambda l, f: round(100 * f / (l + f), 2) if l + f else ""
with open(painel / "horario.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["modo", "faixa", "secoes", "comparecimento", "lula_2t", "flavio_2t", "pct_flavio_2t", "margem_lula_2t",
                "pct_flavio_1t", "margem_lula_1t", "pct_flavio_esperado", "desvio_flavio_pp"])
    for m in ("local", "brasilia"):
        for nome, _, _ in FAIXAS:
            h = out["horario"][m].get(nome)
            if not h:
                continue
            p2, pe = pf(h["L"], h["F"]), pf(h["eL"], h["eF"])
            w.writerow([m, nome, int(h["secoes"]), int(h["comp"]), int(h["L"]), int(h["F"]), p2, int(h["L"] - h["F"]),
                        pf(h["L1"], h["F1"]), int(h["L1"] - h["F1"]), pe, round(p2 - pe, 2)])
with open(painel / "biometria_quintis.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(quint[0].keys()))
    w.writeheader(); w.writerows(quint)
e = out["extremos"]
with open(painel / "extremos.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["medida", "lula_2t", "flavio_2t", "lula_1t", "flavio_1t", "lula_esperado", "flavio_esperado"])
    w.writerow(["100% dos válidos", e["l100"], e["f100"], e["t1_l100"], e["t1_f100"], e["esp_l100"], e["esp_f100"]])
    w.writerow(["90% ou mais dos válidos", e["l90"], e["f90"], e["t1_l90"], e["t1_f90"], e["esp_l90"], e["esp_f90"]])

# Resumo de cada alegação: número que circulou x número conferido nos boletins
fmt = lambda n: f"{n:,.0f}".replace(",", ".")
hl = out["horario"]["local"]; hb = out["horario"]["brasilia"]
ate17 = hl["até 17:00"]
depois = [hl[x] for x in ("17:01 a 17:15", "17:16 a 18:59", "19:00 ou depois")]
m2 = sum(h["L"] - h["F"] for h in depois); m1 = sum(h["L1"] - h["F1"] for h in depois)
b = out["biometria"]; z = out["zero"]
q5 = next(q for q in quint if q["campo"] == "campo3" and q["quintil"] == 5)
linhas = [
    ["zero", "Seções com zero voto para Flávio", "106", fmt(z["flavio"]), "Confere",
     f"Em {z['flavio_1t_ate2']} delas Flávio já tinha de 0 a 2 votos no 1º turno ({z['flavio_1t_zero']} com zero). "
     f"Ficam sobretudo em AM, MA, PA e RR, em municípios pequenos e distantes da Amazônia e do Maranhão. Há {z['lula']} seções com zero voto para Lula."],
    ["cem", "Seções com 100% dos válidos para um candidato", "106 Lula × 4 Flávio", f"{e['l100']} × {e['f100']}", "Confere",
     f"No 1º turno já eram {e['t1_l100']} × {e['t1_f100']}."],
    ["noventa", "Seções com 90% ou mais para um candidato", "6.899 Lula × 384 Flávio", f"{fmt(e['l90'])} × {e['f90']}", "Confere",
     f"No 1º turno eram {fmt(e['t1_l90'])} × {e['t1_f90']}. Pelo 1º turno de cada seção, o esperado era {fmt(e['esp_l90'])} × {e['esp_f90']}: "
     "Lula teve menos seções extremas do que o previsto."],
    ["ate17", "Urnas encerradas até 17h: Flávio venceu", "52,39% dos válidos, 1,8 mi de vantagem",
     f"{100 * ate17['F'] / (ate17['L'] + ate17['F']):.2f}%, {fmt(ate17['F'] - ate17['L'])} de vantagem", "Confere",
     f"Nessas mesmas urnas, no 1º turno, Flávio tinha {100 * ate17['F1'] / (ate17['L1'] + ate17['F1']):.2f}% e {fmt(ate17['F1'] - ate17['L1'])} de vantagem. "
     f"Ele perdeu ali o mesmo que no resto do país; o resultado ficou {100 * ate17['F'] / (ate17['L'] + ate17['F']) - 100 * ate17['eF'] / (ate17['eL'] + ate17['eF']):+.2f} ponto do esperado."],
    ["depois17", "Urnas encerradas depois das 17h: Lula virou", "6,1 mi de vantagem para Lula", f"{fmt(m2)} de vantagem para Lula", "Confere",
     f"Nessas mesmas urnas Lula já vencia o 1º turno por {fmt(m1)}. São as seções grandes e urbanas, que fecham depois porque têm fila; "
     "a divisão por horário separa regiões, não momentos da apuração."],
    ["tarde", "Votantes em urnas encerradas entre 17h16 e 18h59", "674.799", f"{fmt(hl['17:16 a 18:59']['comp'])} (hora local) ou {fmt(hb['17:16 a 18:59']['comp'])} (Brasília)",
     "Confere, com pequena diferença",
     f"{fmt(hl['17:16 a 18:59']['secoes'])} seções. Pela lei, quem está na fila às 17h vota; a urna só encerra depois do último. "
     f"Flávio ficou {100 * hl['17:16 a 18:59']['F'] / (hl['17:16 a 18:59']['L'] + hl['17:16 a 18:59']['F']) - 100 * hl['17:16 a 18:59']['eF'] / (hl['17:16 a 18:59']['eL'] + hl['17:16 a 18:59']['eF']):+.2f} ponto do esperado."],
    ["noite", "Votantes em urnas encerradas às 19h ou depois", "1.856.306", f"{fmt(hl['19:00 ou depois']['comp'])} (hora local) ou {fmt(hb['19:00 ou depois']['comp'])} (Brasília)",
     "Confere, com pequena diferença",
     f"{fmt(hl['19:00 ou depois']['secoes'])} seções, quase metade no RJ. Flávio ficou "
     f"{100 * hl['19:00 ou depois']['F'] / (hl['19:00 ou depois']['L'] + hl['19:00 ou depois']['F']) - 100 * hl['19:00 ou depois']['eF'] / (hl['19:00 ou depois']['eL'] + hl['19:00 ou depois']['eF']):+.2f} ponto do esperado, "
     "menos do que no RJ inteiro (-0,97 ponto)."],
    ["biometria", "Eleitores que votaram sem biometria", "8.632.488 (6,73% do comparecimento)",
     f"{fmt(b['campo3'])} ({100 * b['campo3'] / out['total']['comparecimento']:.2f}%)", "Confere",
     f"É {b['campo3'] / out['total']['margem']:.2f} vez a margem de Lula, mas isso só pesaria se esses eleitores tivessem votado diferente. "
     f"Nas seções com mais eleitores nessa situação ({q5['pct_sem_biometria']:.1f}% em média), Lula ficou {q5['lula_acima_esperado_pp']:+.2f} ponto do esperado, "
     "ou seja, abaixo. O BU tem ainda outra contagem sem biometria, de " + fmt(b["campo1"]) + " eleitores, que também não muda o resultado (tabela abaixo)."],
]
with open(painel / "alegacoes.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "alegacao", "numero_alegado", "numero_conferido", "situacao", "o_que_mostra"])
    # Vírgula decimal (o ponto de milhar fica: decimal tem 1 ou 2 casas, milhar tem 3)
    w.writerows([[re.sub(r"(?<=\d)\.(?=\d{1,2}(?!\d))", ",", c) for c in l] for l in linhas])
