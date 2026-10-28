#!/usr/bin/env python3
"""Manifesto dos arquivos de urna baixados do TSE: um registro por arquivo, com o hash do pacote
informado pelo TSE (aux.json da seção), o SHA-256 calculado aqui e o tamanho. Um arquivo por UF,
para caber no limite de 100 MB do GitHub.

Quem baixar o mesmo arquivo do TSE deve obter o mesmo SHA-256. O "hash TSE" é o identificador do pacote
da seção publicado pelo próprio TSE (é parte da URL de download), não um hash calculado por nós. A URL é
https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/<pleito>/dados/<uf>/<mun>/<zona>/<secao>/<hash>/<arquivo>
(UF em minúsculas e município, zona e seção com os zeros à esquerda, como nas colunas).

Uso: python3 -I manifesto.py <pasta_turno> <prefixo_saida>   ->  <prefixo_saida>_<uf>.csv.gz
"""
import csv
import gzip
import hashlib
import json
import sys
from multiprocessing import Pool
from pathlib import Path


def secao(pasta):
    uf, mun, zona, sec = pasta.parts[-4:]
    hash_tse, st = "", ""
    aux = pasta / "aux.json"
    if aux.exists():
        try:
            a = json.loads(aux.read_text(encoding="utf-8"))
            hs = [h for h in a.get("hashes", []) if h.get("st") in ("Totalizado", "Recebido")] or a.get("hashes", [])
            if hs:
                hash_tse, st = hs[-1].get("hash", ""), hs[-1].get("st", "")
        except ValueError:
            pass
    linhas = []
    for f in sorted(pasta.iterdir()):
        if f.name == "aux.json" or not f.is_file():
            continue
        b = f.read_bytes()
        linhas.append([uf, mun, zona, sec, f.name, len(b), hashlib.sha256(b).hexdigest(), hash_tse, st])
    return linhas


def main():
    pasta, prefixo = Path(sys.argv[1]), sys.argv[2]
    with Pool() as p:
        for uf in sorted(d for d in pasta.iterdir() if d.is_dir()):
            secoes = sorted({a.parent for a in uf.glob("*/*/*/*") if a.name != "aux.json"})
            saida = Path(f"{prefixo}_{uf.name}.csv.gz")
            n = 0
            with gzip.open(saida, "wt", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "ARQUIVO", "BYTES", "SHA256", "HASH_PACOTE_TSE", "SITUACAO_TSE"])
                for linhas in p.imap(secao, secoes, chunksize=500):
                    w.writerows(linhas)
                    n += len(linhas)
            print(saida, len(secoes), "seções,", n, "arquivos", flush=True)


if __name__ == "__main__":
    main()
