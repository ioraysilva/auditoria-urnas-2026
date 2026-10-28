#!/usr/bin/env python3
"""Converte os arquivos -bu.dat baixados por baixar_bu.py em um CSV parecido com o bweb.

O .bu.dat é ASN.1 DER (formato do TSE). O decodificador abaixo é genérico e o
mapeamento de campos foi feito comparando um BU decodificado com o BU impresso
da mesma seção.

Nomes e partidos dos candidatos não estão no BU, só os números; eles são
preenchidos a partir de analise/saida/votos_uf.csv (1º turno), quando existir.

Uso: python3 -I ler_bu.py <pasta_baixada> <saida.csv> [<votos_uf_1t.csv>] [<cargos>]
     <cargos>: lista separada por vírgula para manter só alguns cargos,
     ex.: Presidente,Governador,Senador (padrão: todos)
"""
import csv
import json
import sys
from pathlib import Path

CARGOS = {1: "Presidente", 3: "Governador", 5: "Senador", 6: "Deputado Federal",
          7: "Deputado Estadual", 8: "Deputado Distrital", 11: "Prefeito", 13: "Vereador"}
TIPOS_VOTO = {1: "Nominal", 2: "Branco", 3: "Nulo", 4: "Legenda", 5: "Cargo sem candidato"}


def decodificar(b, i=0, fim=None):
    """Lista de nós (classe, tag, construído, valor|filhos)."""
    fim = len(b) if fim is None else fim
    nos = []
    while i < fim:
        t = b[i]; i += 1
        tag = t & 0x1F
        if tag == 0x1F:
            tag = 0
            while True:
                x = b[i]; i += 1
                tag = (tag << 7) | (x & 0x7F)
                if not x & 0x80:
                    break
        n = b[i]; i += 1
        if n & 0x80:
            k = n & 0x7F
            n = int.from_bytes(b[i:i + k], "big"); i += k
        cons = bool(t & 0x20)
        nos.append((t >> 6, tag, cons, decodificar(b, i, i + n) if cons else b[i:i + n]))
        i += n
    return nos


def inteiro(no):
    return int.from_bytes(no[3], "big", signed=True)


def texto(no):
    return no[3].decode("latin1")


def data(s):
    return f"{s[:4]}-{s[4:6]}-{s[6:8]} {s[9:11]}:{s[11:13]}:{s[13:15]}" if len(s) >= 15 else s


def ler_bu(caminho):
    envelope = decodificar(Path(caminho).read_bytes())[0][3]
    bu = decodificar(envelope[-1][3])[0][3]   # conteúdo: último OCTET STRING do envelope

    urna = bu[2][3]
    corresp = urna[2][3]
    carga = corresp[1][3]
    id_secao = bu[3][3]
    mun_zona = id_secao[0][3]
    # Depois da data de emissão vêm campos opcionais: [0] abertura/encerramento,
    # [1] habilitação (ausente no exterior), um INTEGER de comparecimento e a SEQUENCE de resultados.
    resto = bu[5:]
    abertura = encerramento = ""
    habilitacao = ["", "", ""]
    comparecimento_secao = ""
    for no in resto:
        if no[0] == 2 and no[1] == 0:
            abertura, encerramento = (texto(x) for x in no[3])
        elif no[0] == 2 and no[1] == 1 and len(no[3]) == 3:   # no busa esse [1] tem outro conteúdo
            habilitacao = [inteiro(x) for x in no[3]]
        elif no[0] == 0 and no[1] == 2:
            comparecimento_secao = inteiro(no)
    resultados_eleicoes = next(no for no in resto if no[0] == 0 and no[1] == 16)

    secao = {
        "CD_MUNICIPIO": inteiro(mun_zona[0]), "NR_ZONA": inteiro(mun_zona[1]),
        "NR_LOCAL_VOTACAO": inteiro(id_secao[1]), "NR_SECAO": inteiro(id_secao[2]),
        "VERSAO_URNA": texto(urna[1]), "NR_URNA_EFETIVADA": inteiro(carga[0]),
        "CD_FLASHCARD": carga[1][3].hex().upper(), "DT_CARGA": data(texto(carga[3])),
        "CD_CARGA": texto(carga[4]), "DT_ABERTURA": data(abertura) if abertura else "", "DT_ENCERRAMENTO": data(encerramento) if encerramento else "",
        "DT_EMISSAO_BU": data(texto(bu[4])), "QT_COMPARECIMENTO_SECAO": comparecimento_secao,
        "QT_HAB_SEM_BIOMETRIA": habilitacao[0], "QT_HAB_BIOMETRICA": habilitacao[1],
        "QT_HAB_BIOGRAFICA": habilitacao[2],
    }

    linhas = []
    for eleicao in resultados_eleicoes[3]:
        e = eleicao[3]
        id_eleicao, aptos = inteiro(e[0]), inteiro(e[1])
        resultados = next(x for x in e[2:] if x[1] == 16 and x[0] == 0)   # primeira SEQUENCE após os inteiros
        for res in resultados[3]:
            r = res[3]
            comparecimento = inteiro(r[1])
            for cargo in r[2][3]:
                c = cargo[3]
                cd_cargo = inteiro(c[0])
                for votavel in c[2][3]:
                    v = votavel[3]
                    tipo, votos = inteiro(v[0]), inteiro(v[1])
                    numero = partido = ""
                    if len(v) > 2 and v[2][2] and v[2][1] == 3:     # [3] identificação do votável
                        partido, numero = (inteiro(x) for x in v[2][3])
                    elif tipo == 2:
                        numero = 95
                    elif tipo == 3:
                        numero = 96
                    linhas.append({**secao, "CD_ELEICAO": id_eleicao, "QT_APTOS": aptos,
                                   "QT_COMPARECIMENTO": comparecimento, "CD_CARGO": cd_cargo,
                                   "DS_CARGO": CARGOS.get(cd_cargo, cd_cargo),
                                   "DS_TIPO_VOTAVEL": TIPOS_VOTO.get(tipo, tipo),
                                   "NR_PARTIDO": partido, "NR_VOTAVEL": numero, "QT_VOTOS": votos})
    return linhas


def data_br(d, h):
    return f"{d[6:10]}-{d[3:5]}-{d[0:2]} {h}" if d and h else ""


def recebimento(pasta_secao):
    """Hora de recebimento do arquivo que valeu, lida do aux.json da seção.

    Confere com o DT_BU_RECEBIDO do bweb (ex.: Grajaú 15/377, 1º turno: 19:08:50 nos dois),
    então serve para reconstruir a curva da apuração."""
    try:
        aux = json.loads((pasta_secao / "aux.json").read_bytes())
        h = [x for x in aux.get("hashes", []) if x.get("st") == "Totalizado"] or aux.get("hashes", [])
        return data_br(h[-1].get("dr"), h[-1].get("hr"))
    except (OSError, ValueError, IndexError):
        return ""


def main():
    pasta, saida = Path(sys.argv[1]), Path(sys.argv[2])
    nomes = {}
    if len(sys.argv) > 3:
        with open(sys.argv[3], encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                nomes[(r["SG_UF"], r["CARGO"], r["NR_VOTAVEL"])] = (r["NM_VOTAVEL"], r["SG_PARTIDO"])
    cargos = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None

    campos = None
    erros = 0
    with open(saida, "w", encoding="utf-8", newline="") as f:
        w = None
        # -busa.dat: BU gerado pelo Sistema de Apuração (urna que falhou/votação manual), mesmo formato.
        arquivos = sorted(list(pasta.rglob("*-bu.dat")) + list(pasta.rglob("*-busa.dat")))
        for n, arq in enumerate(arquivos, 1):
            uf_dir, mun, zona, sec = arq.parts[-5:-1]
            uf = uf_dir.upper()
            try:
                linhas = ler_bu(arq)
            except Exception as e:
                erros += 1
                print(f"erro em {arq}: {e!r}", file=sys.stderr)
                continue
            origem = "busa" if arq.name.endswith("-busa.dat") else "bu"
            tempos = {"DT_BU_RECEBIDO": recebimento(arq.parent)}
            for l in linhas:
                if cargos and l["DS_CARGO"] not in cargos:
                    continue
                nm, sg = nomes.get((uf, l["DS_CARGO"], str(l["NR_VOTAVEL"])), ("", ""))
                l = {"SG_UF": uf, "ORIGEM": origem, **l, **tempos, "NM_VOTAVEL": nm, "SG_PARTIDO": sg}
                if w is None:
                    campos = list(l)
                    w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
                    w.writeheader()
                w.writerow(l)
            if n % 20000 == 0:
                print(f"{n:,} BUs lidos", flush=True)
    print(f"Pronto: {saida} ({erros} erros)")


if __name__ == "__main__":
    main()
