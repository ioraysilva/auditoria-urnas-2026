#!/usr/bin/env python3
"""Baixa os arquivos de urna (BU, RDV, log...) do site de resultados do TSE.

Usa os mesmos endereços que o app resultados.tse.jus.br consulta:
  config/<uf>/<uf>-p<pleito>-cs.json          lista de municípios/zonas/seções da UF
  dados/<uf>/<mun>/<zona>/<secao>/...-aux.json  hash e nomes dos arquivos da seção
  dados/<uf>/<mun>/<zona>/<secao>/<hash>/<arq>  o arquivo em si

Grava em <saida>/<uf>/<mun>/<zona>/<secao>/ e pula o que já existe, então
pode ser interrompido e rodado de novo para continuar.

Uso:
  python3 -I baixar_bu.py --saida 2t                  # todas as UFs, só o BU
  python3 -I baixar_bu.py --saida 2t --uf ma --uf pi  # só algumas UFs
  python3 -I baixar_bu.py --saida 2t --tipos bu,rdv   # também o RDV
Tipos disponíveis: bu, rdv, log, vota (log e vota são grandes: ~200 KB e ~60 KB por seção).
"""
import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

UFS = ("ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to zz").split()
RAIZ = "https://resultados.tse.jus.br/oficial/{ano}/arquivo-urna/{pleito}"


# Quando o servidor responde 429, todas as threads param juntas; a pausa dobra
# a cada 429 seguido (1 min, 2, 4... até 15 min) e volta ao normal no primeiro sucesso.
_trava = threading.Lock()
_pausa_ate = 0.0
_pausa = 60


def _esperar_pausa():
    while (resta := _pausa_ate - time.time()) > 0:
        time.sleep(resta)


def get(url, tentativas=5):
    global _pausa_ate, _pausa
    t = 0
    while True:
        _esperar_pausa()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "baixar_bu/1.0"}), timeout=60) as r:
                dados = r.read()
            _pausa = 60
            return dados
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429:  # limite do servidor: pausa geral e tenta de novo, sem desistir da seção
                with _trava:
                    if time.time() >= _pausa_ate:
                        espera = e.headers.get("Retry-After", "")
                        segundos = int(espera) if espera.isdigit() else _pausa
                        _pausa_ate = time.time() + segundos
                        _pausa = min(_pausa * 2, 900)
                        print(f"  429 do servidor: pausando {segundos}s", file=sys.stderr, flush=True)
                continue
            if t == tentativas - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if t == tentativas - 1:
                raise
        time.sleep(2 ** t)
        t += 1


def secoes_da_uf(base, pleito, uf, saida):
    destino = saida / uf / f"{uf}-p{pleito}-cs.json"
    if destino.exists():
        dados = destino.read_bytes()
    else:
        dados = get(f"{base}/config/{uf}/{uf}-p{pleito}-cs.json")
        if dados is None:
            print(f"{uf}: lista de seções não encontrada", file=sys.stderr)
            return []
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)
    cs = json.loads(dados)
    return [(uf, m["cd"], z["cd"], s["ns"]) for a in cs["abr"] for m in a["mu"] for z in m["zon"] for s in z["sec"]]


def baixar_secao(base, pleito, saida, tipos, uf, mun, zona, secao):
    pasta = saida / uf / mun / zona / secao
    url_secao = f"{base}/dados/{uf}/{mun}/{zona}/{secao}"
    aux_path = pasta / "aux.json"
    if aux_path.exists():
        aux = json.loads(aux_path.read_bytes())
    else:
        dados = get(f"{url_secao}/p{pleito}-{uf}-m{mun}-z{zona}-s{secao}-aux.json")
        if dados is None:
            return "sem_aux"
        aux = json.loads(dados)
        pasta.mkdir(parents=True, exist_ok=True)
        aux_path.write_bytes(dados)
    # Uma seção pode ter mais de um hash (reenvio); o último totalizado é o que vale.
    hashes = [h for h in aux.get("hashes", []) if h.get("st") in ("Totalizado", "Recebido")] or aux.get("hashes", [])
    if not hashes:
        return "sem_hash"
    h = hashes[-1]
    if h.get("hash") == "0":                      # seção não instalada / sem arquivo
        return aux.get("st", "sem_arquivo").lower().replace(" ", "_")
    baixados = 0
    for arq in h["arq"]:
        if arq["tp"] not in tipos:
            continue
        destino = pasta / arq["nm"]
        if destino.exists():
            continue
        dados = get(f"{url_secao}/{h['hash']}/{arq['nm']}")
        if dados is None:
            return "arquivo_404"
        destino.write_bytes(dados)
        baixados += 1
    return "ok" if baixados else "ja_existia"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--saida", required=True, type=Path)
    p.add_argument("--uf", action="append", help="UF (minúscula); repetir para várias. Padrão: todas + zz")
    p.add_argument("--pleito", default="3221", help="3221 = 2º turno 2026 (3220 = 1º turno)")
    p.add_argument("--ano", default="ele2026")
    p.add_argument("--tipos", default="bu,busa",
                   help="lista separada por vírgula: bu,busa,rdv,log,vota,logsa,sa (busa = BU do sistema de apuração)")
    p.add_argument("--workers", type=int, default=8, help="downloads simultâneos (padrão 8)")
    a = p.parse_args()

    pleito = a.pleito.zfill(6)
    base = RAIZ.format(ano=a.ano, pleito=a.pleito)
    tipos = set(a.tipos.split(","))
    ufs = [u.lower() for u in a.uf] if a.uf else UFS

    for uf in ufs:
        secoes = secoes_da_uf(base, pleito, uf, a.saida)
        contagem, inicio = {}, time.time()
        with ThreadPoolExecutor(a.workers) as ex:
            futuros = [ex.submit(baixar_secao, base, pleito, a.saida, tipos, *s) for s in secoes]
            for n, f in enumerate(as_completed(futuros), 1):
                try:
                    st = f.result()
                except Exception as e:  # segue com as outras seções; rodar de novo tenta as que falharam
                    st = "erro"
                    print(f"  erro: {e}", file=sys.stderr)
                contagem[st] = contagem.get(st, 0) + 1
                if n % 2000 == 0:
                    print(f"  {uf}: {n:,}/{len(secoes):,} ({n / (time.time() - inicio):.0f} seções/s)", flush=True)
        print(f"{uf}: {len(secoes):,} seções em {time.time() - inicio:.0f}s -> {contagem}", flush=True)


if __name__ == "__main__":
    main()
