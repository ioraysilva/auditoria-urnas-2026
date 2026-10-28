#!/usr/bin/env python3
"""Mostra o progresso geral do baixar_bu.py lendo o log e as listas de seções.

Uso: python3 -I progresso.py [<pasta_saida>]   (padrão: 2t)
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

UFS = ("ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to zz").split()
URL = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/{p}/config/{uf}/{uf}-p00{p}-cs.json"

saida = Path(sys.argv[1] if len(sys.argv) > 1 else "2t")
pleito = "3220" if saida.name == "1t" else "3221"
totais = {}
for uf in UFS:
    cs = saida / uf / f"{uf}-p00{pleito}-cs.json"
    if not cs.exists():  # mesma lista que o baixador grava; ele reaproveita depois
        cs.parent.mkdir(parents=True, exist_ok=True)
        cs.write_bytes(urllib.request.urlopen(URL.format(p=pleito, uf=uf), timeout=60).read())
    d = json.loads(cs.read_bytes())
    totais[uf] = sum(len(z["sec"]) for a in d["abr"] for m in a["mu"] for z in m["zon"])

logs = sorted(saida.glob("download*.log"), key=lambda p: p.stat().st_mtime)
logs = [p for p in logs if "erros" not in p.name and "_v1" not in p.name]
log = logs[-1].read_text() if logs else ""   # o log da passada mais recente
feitas = {m[0]: int(m[1].replace(",", "")) for m in re.findall(r"^(\w\w): ([\d,]+) seções em", log, re.M)}
parcial = re.findall(r"^  (\w\w): ([\d,]+)/[\d,]+ \((\d+) seções/s\)", log, re.M)
atual, n_atual, ritmo = (parcial[-1][0], int(parcial[-1][1].replace(",", "")), int(parcial[-1][2])) if parcial else ("", 0, 0)
if atual in feitas:
    n_atual = 0

total = sum(totais.values())
pronto = sum(feitas.values()) + n_atual
print(f"Progresso: {pronto:,} de {total:,} seções ({100 * pronto / total:.1f}%)")
print(f"UFs concluídas: {len(feitas)}/{len(UFS)} ({', '.join(feitas) or '-'})")
if atual and atual not in feitas:
    print(f"Em andamento: {atual.upper()} {n_atual:,}/{totais[atual]:,}")
bus = sum(1 for _ in saida.rglob("*-bu.dat")) + sum(1 for _ in saida.rglob("*-busa.dat"))
print(f"BUs já no disco: {bus:,} (passada atual: {logs[-1].name if logs else '-'})")
if ritmo:
    resta = (total - pronto) / ritmo
    print(f"Ritmo: ~{ritmo} seções/s, faltam ~{resta / 3600:.1f} h")
