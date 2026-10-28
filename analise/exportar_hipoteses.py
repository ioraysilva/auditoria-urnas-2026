#!/usr/bin/env python3
"""CSVs do painel para as hipóteses levantadas (abstenções, biometria, curva, recontagem RDV).

Uso: python3 -I exportar_hipoteses.py <pasta_relatorios> <pasta_painel>
"""
import csv
import json
import statistics as st
import sys
from pathlib import Path

rel, out = Path(sys.argv[1]), Path(sys.argv[2])


def gravar(nome, cab, linhas):
    with open(out / nome, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cab)
        w.writerows(linhas)


B = list(csv.DictReader(open(rel / "B_urnas_1t_x_2t.csv", encoding="utf-8"), delimiter=";"))
tx = {t: [int(d[f"COMP_{t}"]) / int(d[f"APTOS_{t}"]) for d in B if int(d[f"APTOS_{t}"]) >= 50] for t in ("1T", "2T")}
salto = [d for d in B if int(d["APTOS_2T"]) >= 50 and int(d["DELTA_COMP"]) / int(d["APTOS_2T"]) >= 0.15]
res_salto = sum(int(d["LULA_2T"]) - float(d["LULA_2T_ESPERADO"]) for d in salto)

c = list(csv.DictReader(open(out / "curva.csv", encoding="utf-8")))
pts = [(r["hora"], float(r["pct_flavio_real"]), float(r["pct_flavio_esperado"])) for r in c if int(r["secoes"]) >= 5000]
delta = [(pts[i][0], round(pts[i][1] - pts[i - 1][1], 3), round(pts[i][2] - pts[i - 1][2], 3)) for i in range(1, len(pts))]
dr, de = [x[1] for x in delta], [x[2] for x in delta]
cor = sum((a - st.mean(dr)) * (b - st.mean(de)) for a, b in zip(dr, de)) / (st.pstdev(dr) * st.pstdev(de) * len(dr))
pior = min(delta, key=lambda x: x[1])
gravar("curva_delta.csv", ["hora", "variacao_real_pp", "variacao_esperada_pp"], delta)

bio = json.loads((rel / "biometria.json").read_text())
gravar("biometria.csv", ["decil", "sem_biometria_vs_uf_pp", "sem_biometria_pct", "lula_acima_esperado_pp", "flavio_acima_esperado_pp", "comparecimento_a_mais_pp"],
       bio["decis"])

r = list(csv.DictReader(open(rel / "recontagem_rdv_brasil.csv", encoding="utf-8"), delimiter=";"))
gravar("rdv_brasil.csv", ["secoes", "iguais", "diferentes", "sem_rdv", "rdv_lula", "rdv_flavio", "rdv_brancos", "rdv_nulos"],
       [[len(r), sum(x["SITUACAO"] == "igual" for x in r), sum(x["SITUACAO"] == "DIFERENTE" for x in r), 1,
         *(sum(int(x[k]) for x in r) for k in ("RDV_LULA", "RDV_FLAVIO", "RDV_BRANCOS", "RDV_NULOS"))]])

gravar("hipoteses.csv", ["id", "a", "b", "c", "d", "e", "f"], [
    ["comp98", sum(v >= 0.98 for v in tx["1T"]), sum(v >= 0.98 for v in tx["2T"]), sum(v >= 1 for v in tx["1T"]), sum(v >= 1 for v in tx["2T"]),
     round(100 * st.mean(tx["1T"]), 2), round(100 * st.mean(tx["2T"]), 2)],
    ["salto", len(salto), round(st.mean(100 * (int(d["LULA_2T"]) - float(d["LULA_2T_ESPERADO"])) / int(d["COMP_2T"]) for d in salto), 2),
     round(res_salto), "", "", ""],
    ["curva", len(delta), sum(x < 0 for x in dr), sum(x > 0 for x in dr), round(cor, 4), pior[1], pior[2]],
])
gravar("salto_comparecimento.csv", ["secao", "aptos", "comp_1t", "comp_2t", "lula_1t", "lula_2t", "flavio_1t", "flavio_2t", "lula_esperado"],
       [[f'{d["UF"]}-{d["CD_MUNICIPIO"]}-{d["NR_ZONA"]}-{d["NR_SECAO"]}', d["APTOS_2T"], d["COMP_1T"], d["COMP_2T"], d["LULA_1T"], d["LULA_2T"],
         d["FLAVIO_1T"], d["FLAVIO_2T"], d["LULA_2T_ESPERADO"]]
        for d in sorted(salto, key=lambda d: -(int(d["LULA_2T"]) - float(d["LULA_2T_ESPERADO"])))])

# Referência histórica (recordada, não baixada): líder do 1º turno x vencedor do 2º
hist = [
    ("Brasil", 1989, "Collor", 30.48, "Lula", 17.18, "Collor", 53.03), ("Brasil", 2002, "Lula", 46.44, "Serra", 23.19, "Lula", 61.27),
    ("Brasil", 2006, "Lula", 48.61, "Alckmin", 41.64, "Lula", 60.83), ("Brasil", 2010, "Dilma", 46.91, "Serra", 32.61, "Dilma", 56.05),
    ("Brasil", 2014, "Dilma", 41.59, "Aécio", 33.55, "Dilma", 51.64), ("Brasil", 2018, "Bolsonaro", 46.03, "Haddad", 29.28, "Bolsonaro", 55.13),
    ("Brasil", 2022, "Lula", 48.43, "Bolsonaro", 43.20, "Lula", 50.90),
    ("França", 1981, "Giscard d'Estaing", 28.32, "Mitterrand", 25.85, "Mitterrand", 51.76),
    ("Portugal", 1986, "Freitas do Amaral", 46.31, "Mário Soares", 25.43, "Mário Soares", 51.18),
    ("Colômbia", 2014, "Zuluaga", 29.28, "Santos", 25.69, "Santos", 50.95),
    ("Argentina", 2015, "Scioli", 37.08, "Macri", 34.15, "Macri", 51.34),
    ("Peru", 2016, "Keiko Fujimori", 39.86, "Kuczynski", 21.05, "Kuczynski", 50.12),
    ("Chile", 2021, "Kast", 27.91, "Boric", 25.82, "Boric", 55.87),
    ("Argentina", 2023, "Massa", 36.78, "Milei", 29.99, "Milei", 55.65),
]
u = json.loads((rel / "simulacoes.json").read_text(encoding="utf-8"))["brasil"]
linhas = [[p, a, l1, v1, s1, v2, round(v1 - v2, 2), w, vw, "sim" if w != l1 else "não"] for p, a, l1, v1, s1, v2, w, vw in hist]
linhas.append(["Brasil", 2026, "Flávio", u["pF1"], "Lula", u["pL1"], round(u["pF1"] - u["pL1"], 2), "Lula", u["pL2"], "sim"])
gravar("historico.csv", ["pais", "ano", "lider_1t", "pct_lider_1t", "segundo_1t", "pct_segundo_1t", "vantagem_pp", "vencedor_2t", "pct_vencedor_2t", "virou"],
       sorted(linhas, key=lambda l: (l[0] != "Brasil", l[1])))
print("ok")
