#!/usr/bin/env python3
"""Consolida os Boletins de Urna (bweb) do TSE em totais por candidato.

Lê os CSVs direto de dentro dos .zip (sem extrair), processa uma UF por
processo e grava em <saida>/:

  votos_uf.csv          votos por UF x cargo x votável
  votos_municipio.csv   votos por UF x município x cargo x votável
  votos_brasil.csv      votos somados de todas as UFs (útil para Presidente)
  comparecimento_uf.csv seções, aptos, comparecimento e abstenções por UF x cargo
                        (contados uma vez por seção, sem a repetição por linha)

Uso: python3 -I consolidar.py <pasta_dos_zips> [<pasta_saida>]
"""
import csv
import io
import sys
import zipfile
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

COLS = [
    "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
    "DS_CARGO_PERGUNTA", "SG_PARTIDO", "QT_APTOS", "QT_COMPARECIMENTO",
    "QT_ABSTENCOES", "DS_TIPO_URNA", "DS_TIPO_VOTAVEL", "NR_VOTAVEL",
    "NM_VOTAVEL", "QT_VOTOS",
]


def processar(zip_path):
    votos_mun = defaultdict(int)      # (uf, cd_mun, nm_mun, cargo, tipo, nr, nome, partido) -> votos
    secoes = {}                       # (uf, cargo, cd_mun, zona, secao) -> (aptos, comp, abst, tipo_urna)
    linhas = 0
    with zipfile.ZipFile(zip_path) as z:
        nome_csv = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(nome_csv) as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="latin1", newline=""), delimiter=";")
            cab = next(reader)
            (i_uf, i_cdm, i_nmm, i_zona, i_sec, i_cargo, i_part, i_apt, i_comp,
             i_abst, i_turna, i_tipo, i_nr, i_nome, i_votos) = (cab.index(c) for c in COLS)
            for r in reader:
                linhas += 1
                uf, cdm, cargo = r[i_uf], r[i_cdm], r[i_cargo]
                votos_mun[(uf, cdm, r[i_nmm], cargo, r[i_tipo], r[i_nr], r[i_nome], r[i_part])] += int(r[i_votos])
                chave_sec = (uf, cargo, cdm, r[i_zona], r[i_sec])
                if chave_sec not in secoes:
                    secoes[chave_sec] = (int(r[i_apt]), int(r[i_comp]), int(r[i_abst]), r[i_turna])
    return Path(zip_path).name, linhas, dict(votos_mun), secoes


def main():
    origem = Path(sys.argv[1])
    saida = Path(sys.argv[2]) if len(sys.argv) > 2 else origem / "analise" / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    zips = sorted(origem.glob("bweb_*.zip"), key=lambda p: -p.stat().st_size)  # maiores primeiro

    votos_mun = defaultdict(int)
    comp = defaultdict(lambda: [0, 0, 0, 0, defaultdict(int)])  # (uf, cargo) -> secoes, aptos, comp, abst, tipos de urna
    with Pool() as pool:
        for nome, linhas, vm, secs in pool.imap_unordered(processar, map(str, zips)):
            print(f"{nome}: {linhas:,} linhas, {len(secs):,} seções x cargo", flush=True)
            for k, v in vm.items():
                votos_mun[k] += v
            for (uf, cargo, *_), (apt, cmp_, abst, turna) in secs.items():
                c = comp[(uf, cargo)]
                c[0] += 1; c[1] += apt; c[2] += cmp_; c[3] += abst; c[4][turna] += 1

    votos_uf = defaultdict(int)
    votos_br = defaultdict(int)
    for (uf, _cdm, _nmm, cargo, tipo, nr, nome, part), v in votos_mun.items():
        votos_uf[(uf, cargo, tipo, nr, nome, part)] += v
        votos_br[(cargo, tipo, nr, nome, part)] += v

    def gravar(arquivo, cab, itens):
        with open(saida / arquivo, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(cab)
            w.writerows(itens)

    gravar("votos_municipio.csv",
           ["SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "CARGO", "TIPO_VOTAVEL", "NR_VOTAVEL", "NM_VOTAVEL", "SG_PARTIDO", "VOTOS"],
           (k + (v,) for k, v in sorted(votos_mun.items(), key=lambda kv: (kv[0][0], kv[0][2], kv[0][3], -kv[1]))))
    gravar("votos_uf.csv",
           ["SG_UF", "CARGO", "TIPO_VOTAVEL", "NR_VOTAVEL", "NM_VOTAVEL", "SG_PARTIDO", "VOTOS"],
           (k + (v,) for k, v in sorted(votos_uf.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[1]))))
    gravar("votos_brasil.csv",
           ["CARGO", "TIPO_VOTAVEL", "NR_VOTAVEL", "NM_VOTAVEL", "SG_PARTIDO", "VOTOS"],
           (k + (v,) for k, v in sorted(votos_br.items(), key=lambda kv: (kv[0][0], -kv[1]))))
    gravar("comparecimento_uf.csv",
           ["SG_UF", "CARGO", "SECOES", "APTOS", "COMPARECIMENTO", "ABSTENCOES", "TIPOS_URNA"],
           ((uf, cargo, c[0], c[1], c[2], c[3], " | ".join(f"{t}: {n}" for t, n in sorted(c[4].items())))
            for (uf, cargo), c in sorted(comp.items())))
    print(f"Arquivos gravados em {saida}")


if __name__ == "__main__":
    main()
