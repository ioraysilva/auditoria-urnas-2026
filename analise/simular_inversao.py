#!/usr/bin/env python3
"""Cenário hipotético: o TSE teria invertido os votos de Lula e Flávio antes de publicar,
no Brasil inteiro ou só no Nordeste. Qual cenário explica os dados?

Para cada seção, o 1º turno (que ninguém alega ter sido invertido) prevê o 2º. Se os números
publicados estivessem trocados, os votos publicados de Lula seguiriam os votos de Flávio no 1º turno,
e vice-versa. Testes:
  1. Correlação, seção a seção, entre a % de Lula no 1º turno e a % publicada de Lula no 2º.
  2. Simulação (Monte Carlo): gera 2º turnos "verdadeiros" a partir do 1º turno com o modelo e o ruído
     observados, publica-os trocados ou não, e vê qual cenário reproduz a correlação observada.
  3. Nordeste: modelo treinado fora do Nordeste prevê as seções do Nordeste; compara o erro dos
     números como publicados com o erro dos números trocados (razão de verossimilhança).
  4. Resultado que teria saído em cada cenário.

Uso: python3 -I simular_inversao.py <B_urnas_1t_x_2t.csv> <saida.json> <pasta_painel>
"""
import csv
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from relatorio import mqo

NE = {"AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"}
random.seed(2026)
N_SIM = 200

B, sec = Path(sys.argv[1]), []
for d in csv.DictReader(open(B, encoding="utf-8"), delimiter=";"):
    v = {k: int(d[k]) for k in ("COMP_1T", "COMP_2T", "LULA_1T", "FLAVIO_1T", "OUTROS_1T", "BRANCOS_1T", "NULOS_1T", "LULA_2T", "FLAVIO_2T")}
    if v["COMP_1T"] < 20 or v["COMP_2T"] < 20:
        continue
    v["ne"] = d["UF"] in NE
    sec.append(v)


def corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a)); sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def X(s):
    return [1.0, s["LULA_1T"], s["FLAVIO_1T"], s["OUTROS_1T"], s["BRANCOS_1T"] + s["NULOS_1T"], s["COMP_2T"] - s["COMP_1T"]]


def pl1(s): return s["LULA_1T"] / s["COMP_1T"]
def pl2(s, trocado=False): return (s["FLAVIO_2T"] if trocado else s["LULA_2T"]) / s["COMP_2T"]


out = {}
# 1. correlação observada
for nome, grupo in (("brasil", sec), ("nordeste", [s for s in sec if s["ne"]])):
    out[f"corr_{nome}"] = {"publicado": corr([pl1(s) for s in grupo], [pl2(s) for s in grupo]),
                           "trocado": corr([pl1(s) for s in grupo], [pl2(s, True) for s in grupo])}
# Seções onde quem liderou o 1º turno também lidera o 2º
lider = lambda s, t: (s["LULA_2T"] > s["FLAVIO_2T"]) if not t else (s["FLAVIO_2T"] > s["LULA_2T"])
out["mantem_lider"] = {t: sum(1 for s in sec if (s["LULA_1T"] > s["FLAVIO_1T"]) == lider(s, t)) for t in (False, True)}
out["mantem_lider"] = {"publicado": out["mantem_lider"][False], "trocado": out["mantem_lider"][True], "secoes": len(sec)}

# 2. Monte Carlo com o modelo nacional
cL = mqo([X(s) for s in sec], [s["LULA_2T"] for s in sec])
cF = mqo([X(s) for s in sec], [s["FLAVIO_2T"] for s in sec])
rL = [(s["LULA_2T"] - sum(a * b for a, b in zip(cL, X(s)))) / math.sqrt(s["COMP_2T"]) for s in sec]
rF = [(s["FLAVIO_2T"] - sum(a * b for a, b in zip(cF, X(s)))) / math.sqrt(s["COMP_2T"]) for s in sec]
dpL = math.sqrt(sum(v * v for v in rL) / len(rL)); dpF = math.sqrt(sum(v * v for v in rF) / len(rF))
sims = {"nenhuma": [], "brasil": [], "nordeste": []}
amostra = random.sample(sec, 60000)
for _ in range(N_SIM):
    a, bn, bb, bne = [], [], [], []
    for s in amostra:
        x = X(s); r = math.sqrt(s["COMP_2T"])
        L = max(0, sum(p * q for p, q in zip(cL, x)) + random.gauss(0, dpL) * r)
        F = max(0, sum(p * q for p, q in zip(cF, x)) + random.gauss(0, dpF) * r)
        t = L + F or 1
        a.append(pl1(s)); bn.append(L / t); bb.append(F / t); bne.append(F / t if s["ne"] else L / t)
    sims["nenhuma"].append(corr(a, bn)); sims["brasil"].append(corr(a, bb)); sims["nordeste"].append(corr(a, bne))
obs = corr([pl1(s) for s in amostra], [s["LULA_2T"] / ((s["LULA_2T"] + s["FLAVIO_2T"]) or 1) for s in amostra])
out["monte_carlo"] = {"observado": obs, **{k: {"min": min(v), "max": max(v), "media": sum(v) / len(v),
                                               "dentro": sum(1 for x in v if x >= obs - 0.002)} for k, v in sims.items()}, "n_sim": N_SIM}

# 3. Nordeste: modelo treinado fora do Nordeste
fora = [s for s in sec if not s["ne"]]; ne = [s for s in sec if s["ne"]]
cLf = mqo([X(s) for s in fora], [s["LULA_2T"] for s in fora])
cFf = mqo([X(s) for s in fora], [s["FLAVIO_2T"] for s in fora])
def sse(trocado):
    e = 0.0
    for s in ne:
        x = X(s); r2 = s["COMP_2T"]
        L, F = (s["FLAVIO_2T"], s["LULA_2T"]) if trocado else (s["LULA_2T"], s["FLAVIO_2T"])
        e += ((L - sum(a * b for a, b in zip(cLf, x))) ** 2 + (F - sum(a * b for a, b in zip(cFf, x))) ** 2) / r2
    return e
s0, s1 = sse(False), sse(True)
n = 2 * len(ne)
out["nordeste_fora"] = {"secoes": len(ne), "erro_publicado": math.sqrt(s0 / n), "erro_trocado": math.sqrt(s1 / n),
                        "log10_razao": (n / 2) * math.log10(s1 / s0)}

# 4. Resultado em cada cenário (todas as seções do arquivo, sem filtro)
tot = {"L": 0, "F": 0, "Lne": 0, "Fne": 0}
for d in csv.DictReader(open(B, encoding="utf-8"), delimiter=";"):
    tot["L"] += int(d["LULA_2T"]); tot["F"] += int(d["FLAVIO_2T"])
    if d["UF"] in NE:
        tot["Lne"] += int(d["LULA_2T"]); tot["Fne"] += int(d["FLAVIO_2T"])
cen = {"publicado": (tot["L"], tot["F"]), "brasil": (tot["F"], tot["L"]),
       "nordeste": (tot["L"] - tot["Lne"] + tot["Fne"], tot["F"] - tot["Fne"] + tot["Lne"])}
out["cenarios"] = {k: {"lula": l, "flavio": f, "pct_lula": round(100 * l / (l + f), 2)} for k, (l, f) in cen.items()}
out["nordeste_votos"] = {"lula": tot["Lne"], "flavio": tot["Fne"]}
out["coef_lula_publicado"] = cL

Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))

# CSVs do painel
p = Path(sys.argv[3])
mc = out["monte_carlo"]
with open(p / "inversao.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["cenario", "lula", "flavio", "pct_lula", "corr_simulada_min", "corr_simulada_max", "sims_compativeis", "n_sim"])
    for k, nome in (("publicado", "Sem inversão (como publicado)"), ("brasil", "Invertido no Brasil inteiro"), ("nordeste", "Invertido só no Nordeste")):
        m = mc["nenhuma" if k == "publicado" else k]
        c = out["cenarios"][k]
        w.writerow([nome, c["lula"], c["flavio"], c["pct_lula"], round(m["min"], 4), round(m["max"], 4), m["dentro"], N_SIM])
with open(p / "inversao_testes.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "a", "b", "c", "d"])
    w.writerow(["corr_brasil", round(out["corr_brasil"]["publicado"], 4), round(out["corr_brasil"]["trocado"], 4), round(mc["observado"], 4), ""])
    w.writerow(["corr_nordeste", round(out["corr_nordeste"]["publicado"], 4), round(out["corr_nordeste"]["trocado"], 4), "", ""])
    ml = out["mantem_lider"]
    w.writerow(["lider", ml["publicado"], ml["trocado"], ml["secoes"], round(100 * ml["publicado"] / ml["secoes"], 1)])
    nf = out["nordeste_fora"]
    w.writerow(["nordeste", nf["secoes"], round(nf["erro_publicado"], 3), round(nf["erro_trocado"], 3), round(nf["log10_razao"])])
