#!/usr/bin/env python3
"""Reconta Presidente pelo RDV (registro digital do voto) e compara com o BU da mesma seção.

O -rdv.dat é ASN.1 DER: conteúdo -> eleições -> [idEleição, [votos por cargo]] e cada voto é
(tipoVoto, digitação): tipo 2 = nominal, 3 = branco, 4 = nulo (número digitado que não existe).
A urna grava os votos embaralhados, então o RDV não diz a ordem em que foram dados.
Conferido na seção AM 2097/18/37: RDV 84 Lula, 71 Flávio, 2 brancos, 33 nulos = BU.

Uso: python3 -I recontar_rdv.py <pasta_2t> <saida.csv> [lista.csv com UF;CD_MUNICIPIO;NR_ZONA;NR_SECAO]
     sem lista, reconta todas as seções que têm RDV.
"""
import csv
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ler_bu import decodificar, inteiro, ler_bu

PRESIDENTE = 6258


def contar_rdv(caminho):
    cont = decodificar(Path(caminho).read_bytes())[0][3][2][3]
    # Na urna o bloco de eleições é [1]; no RDV do Sistema de Apuração (seção que usou busa) vem como
    # SEQUENCE universal com dois enumerados a mais em cada eleição. Nos dois casos é o último bloco.
    eleicoes = cont[-1]
    for el in eleicoes[3]:
        e = el[3]
        if inteiro(e[0]) != PRESIDENTE:
            continue
        c = {"L": 0, "F": 0, "B": 0, "N": 0, "O": 0}
        for cargo in e[-1][3]:
            for voto in cargo[3][-1][3]:
                f = voto[3]
                tipo = inteiro(f[0])
                dig = f[1][3].decode("latin1") if len(f) > 1 else ""
                if tipo == 2:
                    c["L" if dig == "13" else "F" if dig == "22" else "O"] += 1
                elif tipo == 3:
                    c["B"] += 1
                else:
                    c["N"] += 1
        return c
    return None


def contar_bu(caminho):
    c = {"L": 0, "F": 0, "B": 0, "N": 0, "O": 0}
    for l in ler_bu(caminho):
        if l["DS_CARGO"] != "Presidente":
            continue
        nr, v = str(l["NR_VOTAVEL"]), l["QT_VOTOS"]
        c["L" if nr == "13" else "F" if nr == "22" else "B" if nr == "95" else "N" if nr == "96" else "O"] += v
    return c


def secao(pasta_secao):
    rdv = next(pasta_secao.glob("*-rdv.dat"), None)
    bu = next(pasta_secao.glob("*-bu.dat"), None) or next(pasta_secao.glob("*-busa.dat"), None)
    uf, mun, zona, sec = pasta_secao.parts[-4:]
    base = [uf.upper(), int(mun), int(zona), int(sec)]
    if not rdv or not bu:
        return base + ["sem RDV" if not rdv else "sem BU"] + [""] * 10
    try:
        r, b = contar_rdv(rdv), contar_bu(bu)
    except Exception as e:
        return base + [f"erro: {e!r}"] + [""] * 10
    if r is None:
        return base + ["RDV sem Presidente"] + [""] * 10
    ok = all(r[k] == b[k] for k in "LFBN")
    return base + ["igual" if ok else "DIFERENTE"] + [r[k] for k in "LFBN"] + [b[k] for k in "LFBN"] + [r["L"] - b["L"], r["F"] - b["F"]]


def main():
    pasta, saida = Path(sys.argv[1]), Path(sys.argv[2])
    if len(sys.argv) > 3:
        with open(sys.argv[3], encoding="utf-8", newline="") as f:
            alvo = [pasta / r["UF"].lower() / r["CD_MUNICIPIO"].zfill(5) / r["NR_ZONA"].zfill(4) / r["NR_SECAO"].zfill(4)
                    for r in csv.DictReader(f, delimiter=";")]
    else:
        alvo = sorted({p.parent for p in pasta.glob("*/*/*/*/*-rdv.dat")})
    with Pool() as p:
        linhas = list(p.imap(secao, alvo, chunksize=200))
    with open(saida, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "SITUACAO", "RDV_LULA", "RDV_FLAVIO", "RDV_BRANCOS", "RDV_NULOS",
                    "BU_LULA", "BU_FLAVIO", "BU_BRANCOS", "BU_NULOS", "DIF_LULA", "DIF_FLAVIO"])
        w.writerows(linhas)
    from collections import Counter
    print(saida, Counter(l[4] if not l[4].startswith("erro") else "erro" for l in linhas))


if __name__ == "__main__":
    main()
