#!/usr/bin/env python3
"""Baixa o resultado oficial divulgado pelo TSE para cada município (Presidente).

Usa o arquivo que o app resultados.tse.jus.br mostra por município:
  ele2026/<eleicao>/dados/<uf>/<uf><mun>-c0001-e<eleicao>-u.json
e grava um CSV com seções, aptos, comparecimento, brancos, nulos e votos por candidato.

Uso: python3 -I baixar_oficial.py <pasta_com_cs.json> <saida.csv> [eleicao] [workers]
     eleicao padrão 6258 (Presidente 2026); a lista de municípios vem dos *-cs.json
     já gravados por baixar_bu.py.
"""
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from baixar_bu import get  # mesma rotina, com pausa automática em 429

pasta, saida = Path(sys.argv[1]), Path(sys.argv[2])
eleicao = sys.argv[3] if len(sys.argv) > 3 else "6258"
workers = int(sys.argv[4]) if len(sys.argv) > 4 else 8
RAIZ = f"https://resultados.tse.jus.br/oficial/ele2026/{eleicao}/dados"

municipios = []
for cs in sorted(pasta.glob("*/*-cs.json")):
    d = json.loads(cs.read_bytes())
    for a in d["abr"]:
        municipios += [(a["cd"], m["cd"], m["nm"]) for m in a["mu"]]


def baixar(item):
    uf, mun, nome = item
    dados = get(f"{RAIZ}/{uf}/{uf}{mun}-c0001-e{eleicao.zfill(6)}-u.json")
    if dados is None:
        return None
    d = json.loads(dados)
    e, v = d["e"], d["v"]
    votos = {}
    for c in d["carg"]:
        for a in c["agr"]:
            for p in a["par"]:
                for x in p["cand"]:
                    votos[x["n"]] = int(x["vap"])
    return {"SG_UF": uf.upper(), "CD_MUNICIPIO": int(mun), "NM_MUNICIPIO": nome,
            "DT_TOTALIZACAO": f"{d['dt']} {d['ht']}", "TOTALIZACAO_FINAL": d.get("tf"),
            "SECOES": int(d["s"]["ts"]), "SECOES_TOTALIZADAS": int(d["s"]["st"]),
            "APTOS": int(e["te"]), "COMPARECIMENTO": int(e["c"]), "ABSTENCOES": int(e["a"]),
            "BRANCOS": int(v["vb"]), "NULOS": int(v["tvn"]), "VALIDOS": int(v["vv"]), "votos": votos}


with ThreadPoolExecutor(workers) as ex:
    linhas = [x for x in ex.map(baixar, municipios) if x]

numeros = sorted({n for l in linhas for n in l["votos"]}, key=int)
with open(saida, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter=";")
    base = [k for k in linhas[0] if k != "votos"]
    w.writerow(base + [f"VOTOS_{n}" for n in numeros])
    for l in linhas:
        w.writerow([l[k] for k in base] + [l["votos"].get(n, 0) for n in numeros])
print(f"{saida}: {len(linhas)} de {len(municipios)} municípios")
