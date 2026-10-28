#!/usr/bin/env python3
"""Reconstrói a curva da apuração a partir do CSV gerado por ler_bu.py.

Ordena as seções pela hora em que o BU foi recebido (DT_BU_RECEBIDO) e
acumula os votos minuto a minuto, como o painel do TSE mostrava na noite
da eleição.

Uso: python3 -I curva_apuracao.py <bu.csv> <saida.csv> [cargo] [UF]
     cargo padrão: Presidente; UF opcional (ex.: MA) para a curva de um estado.
"""
import csv
import sys
from collections import defaultdict

entrada, saida = sys.argv[1], sys.argv[2]
cargo = sys.argv[3] if len(sys.argv) > 3 else "Presidente"
uf_filtro = sys.argv[4].upper() if len(sys.argv) > 4 else None

por_minuto = defaultdict(lambda: defaultdict(int))   # minuto -> votável -> votos
secoes_minuto = defaultdict(int)
nomes = {}
vistas = set()
with open(entrada, encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f, delimiter=";"):
        if r["DS_CARGO"] != cargo or (uf_filtro and r["SG_UF"] != uf_filtro):
            continue
        hora = r["DT_BU_RECEBIDO"][:16]
        if not hora:
            continue
        chave = r["NR_VOTAVEL"] if r["DS_TIPO_VOTAVEL"] in ("Nominal", "Legenda") else r["DS_TIPO_VOTAVEL"]
        nomes[chave] = r["NM_VOTAVEL"] or chave
        por_minuto[hora][chave] += int(r["QT_VOTOS"])
        secao = (r["SG_UF"], r["CD_MUNICIPIO"], r["NR_ZONA"], r["NR_SECAO"])
        if secao not in vistas:
            vistas.add(secao)
            secoes_minuto[hora] += 1

total_secoes = len(vistas)
votaveis = sorted(nomes, key=lambda k: -sum(m.get(k, 0) for m in por_minuto.values()))
nominais = [k for k in votaveis if k not in ("Branco", "Nulo")]
acum = defaultdict(int)
n_secoes = 0
with open(saida, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["HORA", "SECOES_TOTALIZADAS", "PCT_SECOES"]
               + [f"VOTOS_{nomes[k]}" for k in votaveis] + [f"PCT_VALIDOS_{nomes[k]}" for k in nominais])
    for hora in sorted(por_minuto):
        for k, v in por_minuto[hora].items():
            acum[k] += v
        n_secoes += secoes_minuto[hora]
        validos = sum(acum[k] for k in nominais) or 1
        w.writerow([hora, n_secoes, f"{100 * n_secoes / total_secoes:.2f}"]
                   + [acum[k] for k in votaveis] + [f"{100 * acum[k] / validos:.2f}" for k in nominais])
print(f"{saida}: {len(por_minuto)} minutos, {total_secoes:,} seções")
