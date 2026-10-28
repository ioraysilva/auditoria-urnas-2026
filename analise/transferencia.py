#!/usr/bin/env python3
"""De onde vieram os votos de Lula e Flávio no 2º turno, seção a seção.

1. Regressão ecológica: votos de Lula e de Flávio no 2º turno de cada seção explicados pelos votos
   de cada candidato do 1º turno na mesma seção (Cury, Renan, Caiado, Zema, esquerda pequena,
   brancos, nulos) e pela variação do comparecimento. Os coeficientes estimam que fração de cada
   eleitorado foi para cada lado (associação, não prova individual: o voto é secreto).
2. Seções em que Lula ganhou mais votos do que existia de "sobra" (votos de outros candidatos,
   queda de brancos/nulos e eleitores a mais): ali parte do ganho exigiria eleitor de Flávio
   no 1º turno votando em Lula no 2º (ou troca de eleitores entre os turnos).

Uso: python3 -I transferencia.py <pasta_bweb_1t> <B_urnas_1t_x_2t.csv> <saida_dir>
"""
import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from relatorio import mqo

GRUPOS = {"13": "lula", "22": "flavio", "70": "cury", "14": "renan", "55": "caiado", "30": "zema",
          "95": "branco", "96": "nulo", "97": "nulo"}
ESQUERDA = {"80", "16", "21", "29"}   # Samara (UP), Hertz Dias (PSTU), Edmilson Costa (PCB), Rui Costa Pimenta (PCO)
COLS = ["lula", "flavio", "cury", "renan", "caiado", "zema", "esquerda", "outros", "branco", "nulo"]


def ler(zip_path):
    sec = {}
    with zipfile.ZipFile(zip_path) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(nome) as raw:
            r = csv.reader(io.TextIOWrapper(raw, encoding="latin1", newline=""), delimiter=";")
            cab = next(r)
            i = {c: cab.index(c) for c in ("SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "DS_CARGO_PERGUNTA", "NR_VOTAVEL", "QT_VOTOS")}
            for l in r:
                if l[i["DS_CARGO_PERGUNTA"]] != "Presidente":
                    continue
                k = (l[i["SG_UF"]], l[i["CD_MUNICIPIO"]].lstrip("0") or "0", l[i["NR_ZONA"]].lstrip("0") or "0", l[i["NR_SECAO"]].lstrip("0") or "0")
                nr = l[i["NR_VOTAVEL"]]
                g = GRUPOS.get(nr) or ("esquerda" if nr in ESQUERDA else "outros")
                s = sec.setdefault(k, dict.fromkeys(COLS, 0))
                s[g] += int(l[i["QT_VOTOS"]])
    return sec


def main():
    pasta, bfile, saida = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    s1 = {}
    with Pool() as p:
        for parte in p.imap_unordered(ler, sorted(pasta.glob("bweb_1t_*.zip"), key=lambda x: -x.stat().st_size)):
            s1.update(parte)
    X, yL, yF, linhas = [], [], [], []
    sobra = defaultdict(int)
    for d in csv.DictReader(open(bfile, encoding="utf-8"), delimiter=";"):
        k = (d["UF"], d["CD_MUNICIPIO"], d["NR_ZONA"], d["NR_SECAO"])
        a = s1.get(k)
        if not a:
            continue
        dc = int(d["DELTA_COMP"])
        X.append([1.0] + [a[c] for c in COLS] + [dc])
        yL.append(int(d["LULA_2T"])); yF.append(int(d["FLAVIO_2T"]))
        # Sobra disponível para Lula sem tirar de quem votou em Flávio
        bn1 = int(d["BRANCOS_1T"]) + int(d["NULOS_1T"]); bn2 = int(d["BRANCOS_2T"]) + int(d["NULOS_2T"])
        disp = int(d["OUTROS_1T"]) + max(0, bn1 - bn2) + max(0, dc)
        dl = int(d["DELTA_LULA"])
        sobra["secoes"] += 1
        if dl > disp:
            sobra["secoes_excede"] += 1
            sobra["votos_excede"] += dl - disp
            if dl - disp >= 20:
                sobra["secoes_excede_20"] += 1
                linhas.append([d["UF"], d["CD_MUNICIPIO"], d["NR_ZONA"], d["NR_SECAO"], d["COMP_1T"], d["COMP_2T"], d["LULA_1T"], d["LULA_2T"],
                               d["FLAVIO_1T"], d["FLAVIO_2T"], d["OUTROS_1T"], disp, dl, dl - disp])
    cL, cF = mqo(X, yL), mqo(X, yF)
    nomes = ["constante"] + COLS + ["eleitor_a_mais"]
    tot = {c: sum(x[i + 1] for x in X) for i, c in enumerate(COLS)}
    tot["eleitor_a_mais"] = sum(x[-1] for x in X)
    res = {"coef_lula": dict(zip(nomes, cL)), "coef_flavio": dict(zip(nomes, cF)), "totais_1t": tot, "sobra": sobra}
    (Path(saida) / "transferencia.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    linhas.sort(key=lambda l: -l[-1])
    with open(Path(saida) / "lula_acima_da_sobra.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "COMP_1T", "COMP_2T", "LULA_1T", "LULA_2T", "FLAVIO_1T", "FLAVIO_2T",
                    "OUTROS_1T", "SOBRA_DISPONIVEL", "GANHO_LULA", "EXCESSO"])
        w.writerows(linhas)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
