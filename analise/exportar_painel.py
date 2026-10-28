#!/usr/bin/env python3
"""Gera os CSVs pequenos do painel a partir de simulacoes.json, do oficial e dos destaques.

Uso: python3 -I exportar_painel.py <pasta_relatorios> <oficial_2t.csv> <pasta_saida>
"""
import csv
import json
import sys
from pathlib import Path

rel, oficial, saida = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
saida.mkdir(parents=True, exist_ok=True)
s = json.loads((rel / "simulacoes.json").read_text(encoding="utf-8"))


def gravar(nome, cab, linhas):
    with open(saida / nome, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cab)
        w.writerows(linhas)


# Totais: oficial x soma dos BUs x 1º turno (mesmas seções)
of = {"Lula": 0, "Flávio": 0, "Brancos": 0, "Nulos": 0, "Comparecimento": 0}
for r in csv.DictReader(open(oficial, encoding="utf-8"), delimiter=";"):
    of["Lula"] += int(r["VOTOS_13"]); of["Flávio"] += int(r["VOTOS_22"])
    of["Brancos"] += int(r["BRANCOS"]); of["Nulos"] += int(r["NULOS"]); of["Comparecimento"] += int(r["COMPARECIMENTO"])
b = s["brasil"]
bu = {"Lula": b["L2"], "Flávio": b["F2"], "Comparecimento": b["comp2"]}
# brancos e nulos separados vêm do relatório A (BN2 junta os dois)
a = {}
for r in csv.DictReader(open(rel / "A_bu_vs_oficial_municipios.csv", encoding="utf-8"), delimiter=";"):
    for k in r:
        if k.startswith("BU_"):
            try:
                a[k] = a.get(k, 0) + int(r[k])
            except ValueError:
                pass
bu["Brancos"] = a.get("BU_BRANCOS", 0); bu["Nulos"] = a.get("BU_NULOS", 0)
t1 = {"Lula": b["L1"], "Flávio": b["F1"], "Comparecimento": b["comp1"], "Brancos": None, "Nulos": None}
gravar("totais.csv", ["item", "oficial_2t", "soma_bus_2t", "diferenca", "primeiro_turno"],
       [[k, of[k], bu[k], bu[k] - of[k], t1.get(k)] for k in of])
gravar("municipios.csv", ["comparados", "identicos", "divergentes"],
       [[sum(1 for _ in open(rel / "A_bu_vs_oficial_municipios.csv", encoding="utf-8")) - 1,
         sum(1 for r in csv.DictReader(open(rel / "A_bu_vs_oficial_municipios.csv", encoding="utf-8"), delimiter=";")
             if r["SITUACAO"].startswith("igual")),
         sum(1 for r in csv.DictReader(open(rel / "A_bu_vs_oficial_municipios.csv", encoding="utf-8"), delimiter=";")
             if r["SITUACAO"] == "DIVERGENTE")]])

# Desvio de Flávio por UF (real - esperado, em p.p. dos votos Lula+Flávio) e composição das janelas finais
hora = {}
with open(rel.parent / "2t" / "bu_2t.csv", encoding="utf-8") as f:
    r = csv.reader(f, delimiter=";"); cab = next(r); I = {c: i for i, c in enumerate(cab)}
    for l in r:
        if l[I["CD_CARGO"]] == "1" and l[I["NR_VOTAVEL"]] == "13":
            hora[(l[0], l[I["CD_MUNICIPIO"]], l[I["NR_ZONA"]], l[I["NR_SECAO"]])] = l[I["DT_BU_RECEBIDO"]][:15] + "0"
dev, jan = {}, {}
for d in csv.DictReader(open(rel / "B_urnas_1t_x_2t.csv", encoding="utf-8"), delimiter=";"):
    e = int(d["FLAVIO_2T"]) - float(d["FLAVIO_2T_ESPERADO"]); v = int(d["FLAVIO_2T"]) + int(d["LULA_2T"])
    x = dev.setdefault(d["UF"], [0.0, 0]); x[0] += e; x[1] += v
    h = hora.get((d["UF"], d["CD_MUNICIPIO"], d["NR_ZONA"], d["NR_SECAO"]))
    if h:
        y = jan.setdefault(h, {}).setdefault(d["UF"], [0.0, 0]); y[0] += e; y[1] += v
linhas = []
for h in sorted(jan):
    tot = sum(v for _, v in jan[h].values())
    if len([1 for k in hora.values() if k == h]) < 200:
        continue
    for uf, (e, v) in sorted(jan[h].items(), key=lambda kv: -kv[1][1])[:5]:
        linhas.append([h, uf, round(100 * v / tot, 1), round(100 * e / v, 2), round(100 * e / tot, 3)])
gravar("janela_uf.csv", ["janela", "uf", "peso_pct", "desvio_uf_pp", "contribuicao_pp"], linhas)

gravar("uf.csv", ["uf", "lula_1t_pct", "flavio_1t_pct", "lula_2t_pct", "flavio_2t_pct", "lula_1t", "flavio_1t", "outros_1t",
                  "lula_2t", "flavio_2t", "comp_1t", "comp_2t", "ganho_lula", "ganho_flavio", "desvio_flavio_pp"],
       [[uf, u["pL1"], u["pF1"], u["pL2"], u["pF2"], u["L1"], u["F1"], u["O1"], u["L2"], u["F2"], u["comp1"], u["comp2"],
         u["L2"] - u["L1"], u["F2"] - u["F1"], round(100 * dev[uf][0] / dev[uf][1], 2)] for uf, u in s["uf"].items()])

nomes = {"inv_FL": "Inversão Flávio → Lula", "inv_LF": "Inversão Lula → Flávio", "F_caiu30": "Flávio caiu mais de 30%",
         "L_caiu30": "Lula caiu mais de 30%", "F_zerou": "Flávio zerou (tinha 10+)", "fora4": "Fora do esperado (4+ desvios)"}
gravar("marcas.csv", ["marca", "real", "simulado_media", "simulado_min", "simulado_max"],
       [[nomes[k], v["real"], round(v["media"]), v["p2_5"], v["p97_5"]] for k, v in s["marcas"].items()])

gravar("hist.csv", ["faixa", "real", "esperado"], [[f, r, e] for f, r, e in s["hist_var_flavio"]])

gravar("curva.csv", ["hora", "secoes", "pct_flavio_real", "pct_flavio_esperado", "secoes_no_minuto"],
       [[c[0], c[1], c[2], c[3], c[4]] for c in s["curva"]])
gravar("janelas.csv", ["janela", "secoes", "desvio_pp", "acaso_min", "acaso_max"],
       [[j["janela"], j["secoes"], j["desvio"], j["p2_5"], j["p97_5"]] for j in s["janelas"] if j["secoes"] >= 200])
p = s["perm"]
gravar("permutacao.csv", ["teste", "pior_janela_real", "acaso_media", "acaso_min", "acaso_max"],
       [["Resíduos embaralhados no país", round(p["min_real"], 3), round(p["min_pais"]["media"], 3), round(p["min_pais"]["p2_5"], 3), round(p["min_pais"]["p97_5"], 3)],
        ["Resíduos embaralhados dentro da UF", round(p["min_real"], 3), round(p["min_uf"]["media"], 3), round(p["min_uf"]["p2_5"], 3), round(p["min_uf"]["p97_5"], 3)]])
gravar("injecao.csv", ["troca_pct", "votos_movidos", "pior_janela_pp"],
       [[c["pct"], c["votos_movidos"], c["desvio_min"]] for c in s["injecao"]["cenarios"]])

c = s["comparecimento"]
gravar("comparecimento.csv", ["medida", "valor"],
       [["Variação do comparecimento", c["delta_comp"]], ["Abstenções 1º turno", c["abst1"]], ["Abstenções 2º turno", c["abst2"]],
        ["Seções onde o comparecimento subiu", c["subiu"]], ["Seções onde caiu", c["caiu"]],
        ["Lula por eleitor a mais", round(c["coefL"], 3)], ["Flávio por eleitor a mais", round(c["coefF"], 3)],
        ["Votos de Lula ligados ao comparecimento", round(c["efeitoL"])], ["Votos de Flávio ligados ao comparecimento", round(c["efeitoF"])],
        ["Margem de Lula", c["margem"]], ["Margem sem o efeito do comparecimento", round(c["margem_sem_efeito"])],
        ["Seções alvo da troca simulada", s["injecao"]["secoes_alvo"]]])
gravar("decis.csv", ["decil", "delta_comp", "delta_lula", "delta_flavio", "secoes"],
       [[i + 1, round(d[0], 1), round(d[1], 1), round(d[2], 1), d[3]] for i, d in enumerate(c["decis"])])

dest = list(csv.DictReader(open(rel / "B_urnas_destaques.csv", encoding="utf-8"), delimiter=";"))
dest = [d for d in dest if "fora do esperado" in d["MARCAS"] or "zerou" in d["MARCAS"]]
dest.sort(key=lambda d: float(d["Z_FLAVIO"]))
gravar("destaques.csv", ["secao", "uf", "municipio", "zona", "num_secao", "comp_1t", "comp_2t", "lula_1t", "lula_2t",
                         "flavio_1t", "flavio_2t", "flavio_esperado", "z", "marcas"],
       [[f'{d["UF"]}-{d["CD_MUNICIPIO"]}-{d["NR_ZONA"]}-{d["NR_SECAO"]}', d["UF"], d["CD_MUNICIPIO"], d["NR_ZONA"], d["NR_SECAO"],
         d["COMP_1T"], d["COMP_2T"], d["LULA_1T"], d["LULA_2T"], d["FLAVIO_1T"], d["FLAVIO_2T"], d["FLAVIO_2T_ESPERADO"],
         d["Z_FLAVIO"], d["MARCAS"]] for d in dest[:40]])
print("ok", sorted(p.name for p in saida.glob("*.csv")))

# ---------- Pontos de atenção (transferencia.json vem de transferencia.py) ----------
t = json.loads((rel / "transferencia.json").read_text(encoding="utf-8"))
cL, cF, t1, sob = t["coef_lula"], t["coef_flavio"], t["totais_1t"], t["sobra"]
grupos = [("cury", "Augusto Cury (Avante)"), ("renan", "Renan Santos (Missão)"), ("caiado", "Ronaldo Caiado (PSD)"),
          ("zema", "Zema (Novo)"), ("esquerda", "Esquerda pequena (UP, PSTU, PCB, PCO)"), ("branco", "Brancos"),
          ("nulo", "Nulos"), ("eleitor_a_mais", "Eleitores a mais no 2º turno")]
gravar("transferencia.csv", ["grupo", "votos_1t", "pct_lula", "pct_flavio", "votos_lula_est", "votos_flavio_est"],
       [[n, t1[g], round(100 * cL[g], 1), round(100 * cF[g], 1), round(cL[g] * t1[g]), round(cF[g] * t1[g])] for g, n in grupos])
acima = list(csv.DictReader(open(rel / "lula_acima_da_sobra.csv", encoding="utf-8"), delimiter=";"))
gravar("acima_sobra.csv", ["secao", "comp_1t", "comp_2t", "lula_1t", "lula_2t", "flavio_1t", "flavio_2t", "sobra", "ganho_lula", "excesso"],
       [[f'{d["UF"]}-{d["CD_MUNICIPIO"]}-{d["NR_ZONA"]}-{d["NR_SECAO"]}', d["COMP_1T"], d["COMP_2T"], d["LULA_1T"], d["LULA_2T"],
         d["FLAVIO_1T"], d["FLAVIO_2T"], d["SOBRA_DISPONIVEL"], d["GANHO_LULA"], d["EXCESSO"]] for d in acima])
gL, gF = b["L2"] - b["L1"], b["F2"] - b["F1"]
fora_neg = [d for d in csv.DictReader(open(rel / "B_urnas_destaques.csv", encoding="utf-8"), delimiter=";")
            if "fora do esperado" in d["MARCAS"] and float(d["Z_FLAVIO"]) < 0]
am = next(d for d in fora_neg if (d["UF"], d["CD_MUNICIPIO"], d["NR_ZONA"], d["NR_SECAO"]) == ("AM", "2097", "18", "37"))
rj21 = next(l for l in linhas if l[0].endswith("21:00") and l[1] == "RJ")
j21 = next(j for j in s["janelas"] if j["janela"].endswith("21:00"))
mk = s["marcas"]
bn_lula = cL["branco"] * t1["branco"] + cL["nulo"] * t1["nulo"]
bn_flav = cF["branco"] * t1["branco"] + cF["nulo"] * t1["nulo"]
pontos = [
    ["ganho", gL, gF, gL + gF, round(100 * gL / (gL + gF), 1), b["O1"], b["BN1"] - b["BN2"]],
    ["direita", round(100 * cL["caiado"], 1), round(100 * cL["renan"], 1), round(100 * cL["cury"], 1), round(100 * cL["zema"], 1),
     round(cL["caiado"] * t1["caiado"] + cL["renan"] * t1["renan"] + cL["cury"] * t1["cury"]), ""],
    ["brancos", b["BN1"], round(bn_lula), round(bn_flav), b["BN1"] - b["BN2"], "", ""],
    ["excesso", sob["secoes_excede"], sob["votos_excede"], sob["secoes_excede_20"], sob["secoes"], "", ""],
    ["fora", mk["fora4"]["real"], round(mk["fora4"]["media"]), len(fora_neg),
     sum(1 for d in fora_neg if d["UF"] in ("AC", "RR")), "", ""],
    ["secao", am["FLAVIO_1T"], am["FLAVIO_2T"], am["LULA_1T"], am["LULA_2T"], am["COMP_1T"], am["COMP_2T"]],
    ["inversao", mk["inv_FL"]["real"], round(mk["inv_FL"]["media"]), mk["inv_FL"]["real"] - round(mk["inv_FL"]["media"]), mk["inv_FL"]["p97_5"], "", ""],
    ["janela", round(j21["desvio"], 2), round(p["min_pais"]["p2_5"], 2), rj21[2], rj21[3], "", ""],
    ["rj", round(100 * dev["RJ"][0] / dev["RJ"][1], 2), "", "", "", "", ""],
]
gravar("pontos.csv", ["id", "a", "b", "c", "d", "e", "f"], pontos)
print("pontos ok")
