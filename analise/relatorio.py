#!/usr/bin/env python3
"""Relatórios de Presidente cruzando 1º turno (bweb), 2º turno (BUs) e o resultado oficial.

A  BUs x resultado oficial por município: a soma dos boletins de urna bate com o
   que o TSE divulgou? (teste direto de alteração na totalização)
B  Mesma seção no 1º e no 2º turno: variação de votos, quedas, zeragens e
   inversões, e o quanto cada seção foge do esperado pelo próprio 1º turno.
C  Comparecimento: para onde foram, em média, os eleitores a mais do 2º turno.
D  Curva da apuração na ordem de recebimento dos BUs, e em cada janela de 10 min
   a % real de Flávio contra a % esperada para aquelas mesmas seções.

Uso: python3 -I relatorio.py <bu_2t.csv> <oficial_2t.csv> <pasta_bweb_1t> <saida>
"""
import csv
import io
import math
import sys
import zipfile
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

LULA, FLAVIO = "13", "22"


# ---------- leitura ----------

def ler_bweb(zip_path):
    """Seções do 1º turno (Presidente) de um zip bweb."""
    secoes = {}
    with zipfile.ZipFile(zip_path) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(nome) as raw:
            r = csv.reader(io.TextIOWrapper(raw, encoding="latin1", newline=""), delimiter=";")
            cab = next(r)
            i = {c: cab.index(c) for c in ("SG_UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "DS_CARGO_PERGUNTA",
                                           "QT_APTOS", "QT_COMPARECIMENTO", "NR_VOTAVEL", "QT_VOTOS", "DT_BU_RECEBIDO")}
            for l in r:
                if l[i["DS_CARGO_PERGUNTA"]] != "Presidente":
                    continue
                k = (l[i["SG_UF"]], int(l[i["CD_MUNICIPIO"]]), int(l[i["NR_ZONA"]]), int(l[i["NR_SECAO"]]))
                s = secoes.get(k)
                if s is None:
                    s = secoes[k] = {"aptos": int(l[i["QT_APTOS"]]), "comp": int(l[i["QT_COMPARECIMENTO"]]),
                                     "L": 0, "F": 0, "O": 0, "B": 0, "N": 0, "hora": l[i["DT_BU_RECEBIDO"]]}
                nr, v = l[i["NR_VOTAVEL"]], int(l[i["QT_VOTOS"]])
                s["L" if nr == LULA else "F" if nr == FLAVIO else "B" if nr == "95" else "N" if nr in ("96", "97") else "O"] += v
    return secoes


def carregar_1t(pasta, cache):
    if cache.exists():
        secoes = {}
        with open(cache, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                k = (r["UF"], int(r["MUN"]), int(r["ZONA"]), int(r["SECAO"]))
                secoes[k] = {c: (r[c] if c == "hora" else int(r[c])) for c in ("aptos", "comp", "L", "F", "O", "B", "N", "hora")}
        return secoes
    secoes = {}
    with Pool() as p:
        for parte in p.imap_unordered(ler_bweb, sorted(pasta.glob("bweb_1t_*.zip"), key=lambda x: -x.stat().st_size)):
            secoes.update(parte)
    with open(cache, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["UF", "MUN", "ZONA", "SECAO", "aptos", "comp", "L", "F", "O", "B", "N", "hora"])
        for k, s in secoes.items():
            w.writerow(list(k) + [s[c] for c in ("aptos", "comp", "L", "F", "O", "B", "N", "hora")])
    return secoes


def carregar_2t(caminho):
    secoes = {}
    with open(caminho, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["DS_CARGO"] != "Presidente":
                continue
            k = (r["SG_UF"], int(r["CD_MUNICIPIO"]), int(r["NR_ZONA"]), int(r["NR_SECAO"]))
            s = secoes.get(k)
            if s is None:
                s = secoes[k] = {"aptos": int(r["QT_APTOS"]), "comp": int(r["QT_COMPARECIMENTO"]), "L": 0, "F": 0,
                                 "O": 0, "B": 0, "N": 0, "hora": r["DT_BU_RECEBIDO"], "urna": r["NR_URNA_EFETIVADA"],
                                 "origem": r["ORIGEM"]}
            nr, v, tipo = r["NR_VOTAVEL"], int(r["QT_VOTOS"]), r["DS_TIPO_VOTAVEL"]
            s["L" if nr == LULA else "F" if nr == FLAVIO else "B" if tipo == "Branco" else "N" if tipo == "Nulo" else "O"] += v
    return secoes


# ---------- estatística (mínimos quadrados, sem bibliotecas) ----------

def mqo(X, y, pesos=None):
    k = len(X[0])
    A = [[0.0] * k for _ in range(k)]
    b = [0.0] * k
    for n, (x, yi) in enumerate(zip(X, y)):
        p = pesos[n] if pesos else 1.0
        for i in range(k):
            b[i] += p * x[i] * yi
            for j in range(k):
                A[i][j] += p * x[i] * x[j]
    for i in range(k):  # eliminação de Gauss
        piv = max(range(i, k), key=lambda r: abs(A[r][i]))
        A[i], A[piv], b[i], b[piv] = A[piv], A[i], b[piv], b[i]
        for r in range(i + 1, k):
            f = A[r][i] / A[i][i]
            b[r] -= f * b[i]
            for c in range(i, k):
                A[r][c] -= f * A[i][c]
    coef = [0.0] * k
    for i in reversed(range(k)):
        coef[i] = (b[i] - sum(A[i][j] * coef[j] for j in range(i + 1, k))) / A[i][i]
    return coef


def pct(a, b):
    return 100 * a / b if b else 0.0


def escrever(caminho, cab, linhas):
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cab)
        w.writerows(linhas)


# ---------- relatórios ----------

def relatorio_a(s2, oficial_csv, saida, resumo):
    bu = defaultdict(lambda: defaultdict(int))
    for (uf, mun, _, _), s in s2.items():
        m = bu[(uf, mun)]
        m["SECOES"] += 1
        for c, col in (("aptos", "APTOS"), ("comp", "COMPARECIMENTO"), ("B", "BRANCOS"), ("N", "NULOS"), ("L", "VOTOS_13"), ("F", "VOTOS_22")):
            m[col] += s[c]
    cols = ["SECOES", "APTOS", "COMPARECIMENTO", "BRANCOS", "NULOS", "VOTOS_13", "VOTOS_22"]
    linhas, completos, divergentes, incompletos = [], 0, [], 0
    tot_of, tot_bu = defaultdict(int), defaultdict(int)
    with open(oficial_csv, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            k = (r["SG_UF"], int(r["CD_MUNICIPIO"]))
            of = {c: int(r[c]) for c in cols}
            b = bu.get(k, {})
            for c in cols:
                tot_of[c] += of[c]
                tot_bu[c] += b.get(c, 0)
            difs = {c: b.get(c, 0) - of[c] for c in cols}
            votos_iguais = not any(difs[c] for c in cols if c not in ("SECOES", "APTOS"))
            # O oficial conta também seções agregadas a outra urna ou não instaladas (aptos sem urna),
            # que não têm BU próprio; nelas só seções/aptos diferem, nunca votos.
            if votos_iguais:
                situacao = "igual" if difs["SECOES"] == 0 and difs["APTOS"] == 0 else \
                    "igual nos votos (seções agregadas/não instaladas sem BU)"
                completos += 1
            elif difs["COMPARECIMENTO"] < 0 and all(difs[c] <= 0 for c in cols):
                situacao = "incompleto (faltam BUs baixados)"
                incompletos += 1
            else:
                situacao = "DIVERGENTE"
                divergentes.append(k)
            linhas.append([r["SG_UF"], r["CD_MUNICIPIO"], r["NM_MUNICIPIO"], situacao]
                          + [of[c] for c in cols] + [b.get(c, 0) for c in cols] + [difs[c] for c in cols])
    escrever(saida / "A_bu_vs_oficial_municipios.csv",
             ["UF", "CD_MUNICIPIO", "MUNICIPIO", "SITUACAO"] + [f"OFICIAL_{c}" for c in cols]
             + [f"BU_{c}" for c in cols] + [f"DIF_{c}" for c in cols], linhas)
    resumo.append("## A. Soma dos boletins de urna x resultado oficial do TSE (Presidente, 2º turno)\n")
    resumo.append(f"- Municípios comparados: {len(linhas):,}")
    resumo.append(f"- **Idênticos nos votos** (comparecimento, brancos, nulos, Lula e Flávio iguais): **{completos:,}**")
    resumo.append(f"- **Divergentes** (soma dos BUs diferente do oficial sem ser só falta de BU): **{len(divergentes):,}**")
    resumo.append(f"- Incompletos (algum BU não baixado: tudo menor que o oficial, nada maior): {incompletos:,}")
    resumo.append("\n| | Oficial TSE | Soma dos BUs | Diferença |\n|---|---:|---:|---:|")
    for c, nome in (("SECOES", "Seções"), ("COMPARECIMENTO", "Comparecimento"), ("VOTOS_13", "Lula"), ("VOTOS_22", "Flávio"),
                    ("BRANCOS", "Brancos"), ("NULOS", "Nulos")):
        resumo.append(f"| {nome} | {tot_of[c]:,} | {tot_bu[c]:,} | {tot_bu[c] - tot_of[c]:+,} |")
    if divergentes:
        resumo.append(f"\nMunicípios divergentes (até 20): {', '.join(f'{u}-{m}' for u, m in divergentes[:20])}")
    resumo.append("\nArquivo: `A_bu_vs_oficial_municipios.csv`\n")


def relatorio_b_c(s1, s2, saida, resumo):
    chaves = [k for k in s2 if k in s1]
    so2 = len(s2) - len(chaves)
    so1 = sum(1 for k in s1 if k not in s2)

    # Modelo do esperado: votos do 2º turno de cada candidato explicados pelo 1º turno da mesma seção.
    X = [[1.0, s1[k]["L"], s1[k]["F"], s1[k]["O"], s1[k]["B"] + s1[k]["N"], s2[k]["comp"] - s1[k]["comp"]] for k in chaves]
    coefF = mqo(X, [s2[k]["F"] for k in chaves])
    coefL = mqo(X, [s2[k]["L"] for k in chaves])
    prevF = {k: sum(a * b for a, b in zip(coefF, x)) for k, x in zip(chaves, X)}
    prevL = {k: sum(a * b for a, b in zip(coefL, x)) for k, x in zip(chaves, X)}
    # Desvio padronizado pelo tamanho da seção (seções grandes variam mais em votos absolutos).
    res = {k: (s2[k]["F"] - prevF[k]) / math.sqrt(max(s2[k]["comp"], 1)) for k in chaves}
    dp = math.sqrt(sum(v * v for v in res.values()) / len(res))

    linhas, flags = [], defaultdict(int)
    destaques = []
    for k in chaves:
        a, b = s1[k], s2[k]
        z = res[k] / dp
        marcas = []
        if a["F"] >= 10 and b["F"] == 0:
            marcas.append("Flávio zerou")
        if a["F"] > a["L"] and b["L"] > b["F"]:
            marcas.append("inversão F→L")
        if a["L"] > a["F"] and b["F"] > b["L"]:
            marcas.append("inversão L→F")
        if a["F"] >= 20 and b["F"] < 0.7 * a["F"]:
            marcas.append("Flávio caiu >30%")
        if a["L"] >= 20 and b["L"] < 0.7 * a["L"]:
            marcas.append("Lula caiu >30%")
        if abs(z) >= 4:
            marcas.append(f"fora do esperado ({'Flávio abaixo' if z < 0 else 'Flávio acima'})")
        for m in marcas:
            flags[m.split(" (")[0] if m.startswith("fora") else m] += 1
        linha = [*k, b.get("urna", ""), b.get("origem", ""), a["aptos"], a["comp"], a["L"], a["F"], a["O"], a["B"], a["N"],
                 b["aptos"], b["comp"], b["L"], b["F"], b["B"], b["N"], b["comp"] - a["comp"], b["L"] - a["L"], b["F"] - a["F"],
                 round(prevF[k], 1), round(prevL[k], 1), round(z, 2), " | ".join(marcas)]
        linhas.append(linha)
        if marcas:
            destaques.append(linha)
    cab = ["UF", "CD_MUNICIPIO", "NR_ZONA", "NR_SECAO", "URNA_2T", "ORIGEM_2T", "APTOS_1T", "COMP_1T", "LULA_1T", "FLAVIO_1T",
           "OUTROS_1T", "BRANCOS_1T", "NULOS_1T", "APTOS_2T", "COMP_2T", "LULA_2T", "FLAVIO_2T", "BRANCOS_2T", "NULOS_2T",
           "DELTA_COMP", "DELTA_LULA", "DELTA_FLAVIO", "FLAVIO_2T_ESPERADO", "LULA_2T_ESPERADO", "Z_FLAVIO", "MARCAS"]
    escrever(saida / "B_urnas_1t_x_2t.csv", cab, linhas)
    destaques.sort(key=lambda l: l[-2])
    escrever(saida / "B_urnas_destaques.csv", cab, destaques)

    tot = lambda t, c: sum((s1 if t == 1 else s2)[k][c] for k in chaves)
    resumo.append("## B. Mesma seção no 1º e no 2º turno (Presidente)\n")
    resumo.append(f"- Seções presentes nos dois turnos: {len(chaves):,} (só no 2º: {so2:,}; só no 1º: {so1:,} — "
                  "seções agregadas/desagregadas ou BUs ainda não baixados)")
    resumo.append(f"- Nessas seções: Flávio {tot(1, 'F'):,} → {tot(2, 'F'):,} ({tot(2, 'F') - tot(1, 'F'):+,}); "
                  f"Lula {tot(1, 'L'):,} → {tot(2, 'L'):,} ({tot(2, 'L') - tot(1, 'L'):+,})")
    resumo.append("- Modelo do esperado (votos do 2º turno explicados pelo 1º turno da mesma seção: Lula, Flávio, outros, "
                  "brancos+nulos e variação de comparecimento):")
    nomes = ["constante", "Lula 1T", "Flávio 1T", "outros 1T", "brancos+nulos 1T", "Δ comparecimento"]
    resumo.append("\n| Termo | Flávio 2T | Lula 2T |\n|---|---:|---:|")
    for n, cf, cl in zip(nomes, coefF, coefL):
        resumo.append(f"| {n} | {cf:.3f} | {cl:.3f} |")
    resumo.append("\n- Contagem de marcas (uma seção pode ter várias):")
    for m, n in sorted(flags.items(), key=lambda x: -x[1]):
        resumo.append(f"  - {m}: {n:,}")
    resumo.append("\n\"Fora do esperado\" = |z| ≥ 4, ou seja, a seção desvia 4 desvios-padrão do previsto pelo próprio 1º turno. "
                  "Em ~500 mil seções, algumas dezenas assim são normais por acaso; centenas concentradas num lugar merecem olhar.")
    resumo.append("\nArquivos: `B_urnas_1t_x_2t.csv` (todas), `B_urnas_destaques.csv` (só as marcadas, das mais negativas para Flávio)\n")

    # C. comparecimento
    resumo.append("## C. Eleitores a mais no 2º turno (comparecimento)\n")
    dcomp = tot(2, "comp") - tot(1, "comp")
    resumo.append(f"- Nas seções comparáveis, o comparecimento variou {dcomp:+,}; Lula {tot(2, 'L') - tot(1, 'L'):+,}; "
                  f"Flávio {tot(2, 'F') - tot(1, 'F'):+,}; votos de outros candidatos no 1º turno: {tot(1, 'O'):,}; "
                  f"brancos+nulos {tot(1, 'B') + tot(1, 'N'):,} → {tot(2, 'B') + tot(2, 'N'):,}")
    i = nomes.index("Δ comparecimento")
    resumo.append(f"- Pelo modelo acima, **cada eleitor a mais numa seção está associado a {coefL[i]:+.2f} voto para Lula e "
                  f"{coefF[i]:+.2f} para Flávio** (média entre seções; é associação, não prova de quem votou em quem — o voto é secreto).")
    faixas = sorted(chaves, key=lambda k: s2[k]["comp"] - s1[k]["comp"])
    resumo.append("\n| Faixa de Δ comparecimento (quintis) | Seções | Δ comp médio | Δ Lula médio | Δ Flávio médio |\n|---|---:|---:|---:|---:|")
    n = len(faixas)
    linhas_c = []
    for q in range(5):
        grupo = faixas[q * n // 5:(q + 1) * n // 5]
        if not grupo:
            continue
        m = lambda c: sum(s2[k][c] - s1[k][c] for k in grupo) / len(grupo)
        resumo.append(f"| Q{q + 1} | {len(grupo):,} | {m('comp'):+.1f} | {m('L'):+.1f} | {m('F'):+.1f} |")
        linhas_c.append([f"Q{q + 1}", len(grupo), round(m("comp"), 2), round(m("L"), 2), round(m("F"), 2)])
    escrever(saida / "C_comparecimento_quintis.csv", ["QUINTIL", "SECOES", "DELTA_COMP_MEDIO", "DELTA_LULA_MEDIO", "DELTA_FLAVIO_MEDIO"], linhas_c)
    resumo.append("")
    return prevF, prevL


def curva(secoes, arquivo):
    por_min = defaultdict(lambda: [0, 0, 0, 0, 0])
    for s in secoes.values():
        if not s["hora"]:
            continue
        m = por_min[s["hora"][:16]]
        m[0] += 1; m[1] += s["L"]; m[2] += s["F"]; m[3] += s["B"] + s["N"]; m[4] += s["O"]
    total = sum(m[0] for m in por_min.values())
    ac = [0, 0, 0, 0, 0]
    linhas = []
    for h in sorted(por_min):
        ac = [a + b for a, b in zip(ac, por_min[h])]
        val = ac[1] + ac[2] + ac[4]
        linhas.append([h, ac[0], round(pct(ac[0], total), 2), ac[1], ac[2], round(pct(ac[1], val), 2), round(pct(ac[2], val), 2)])
    escrever(arquivo, ["HORA", "SECOES_ACUM", "PCT_SECOES", "LULA_ACUM", "FLAVIO_ACUM", "PCT_LULA", "PCT_FLAVIO"], linhas)
    return linhas


def relatorio_d(s1, s2, prevF, prevL, saida, resumo):
    c2 = curva(s2, saida / "D_curva_2t.csv")
    curva(s1, saida / "D_curva_1t.csv")
    janelas = defaultdict(lambda: [0, 0, 0, 0.0, 0.0, 0])
    for k, s in s2.items():
        if not s["hora"]:
            continue
        h = s["hora"][:15] + "0"  # janela de 10 minutos
        j = janelas[h]
        j[0] += 1; j[1] += s["L"]; j[2] += s["F"]
        if k in prevF:
            j[3] += prevF[k]; j[4] += prevL[k]; j[5] += s["L"] + s["F"]
    linhas, maiores = [], []
    for h in sorted(janelas):
        n, L, F, pF, pL, comparaveis = janelas[h]
        real = pct(F, L + F)
        esperado = pct(pF, pF + pL) if pF + pL > 0 else float("nan")
        dif = real - esperado
        linhas.append([h, n, L, F, round(real, 2), round(esperado, 2), round(dif, 2)])
        if n >= 200 and not math.isnan(dif):
            maiores.append((dif, h, n, real, esperado))
    escrever(saida / "D_janelas_10min_2t.csv", ["JANELA", "SECOES", "LULA", "FLAVIO", "PCT_FLAVIO_REAL", "PCT_FLAVIO_ESPERADO", "DIFERENCA_PP"], linhas)
    resumo.append("## D. Curva da apuração (ordem de recebimento dos BUs)\n")
    if c2:
        marcos = [l for l in c2 if l[2] >= 0][::max(1, len(c2) // 12)] + [c2[-1]]
        resumo.append("| Hora | % seções | Lula | Flávio |\n|---|---:|---:|---:|")
        for l in marcos:
            resumo.append(f"| {l[0][11:]} | {l[2]:.1f}% | {l[5]:.2f}% | {l[6]:.2f}% |")
    if maiores:
        difs = [m[0] for m in maiores]
        media = sum(difs) / len(difs)
        resumo.append(f"\n- Janelas de 10 min com ≥200 seções: {len(maiores)}. Diferença média entre a % real de Flávio e a "
                      f"% esperada para aquelas mesmas seções (pelo 1º turno delas): **{media:+.2f} p.p.**; "
                      f"menor {min(difs):+.2f} p.p., maior {max(difs):+.2f} p.p.")
        resumo.append("- Se a totalização tivesse tirado votos de Flávio em certos momentos, as janelas desses momentos "
                      "apareceriam com diferença bem negativa **e** a soma dos BUs não bateria com o oficial (relatório A). "
                      "As oscilações da curva em si vêm de *quais* seções chegam em cada momento (região, fuso, capital x interior).")
        resumo.append("\n| Janelas mais desfavoráveis a Flávio | Seções | % real | % esperada | Dif. |\n|---|---:|---:|---:|---:|")
        for d, h, n, r, e in sorted(maiores)[:8]:
            resumo.append(f"| {h[11:]} | {n:,} | {r:.2f}% | {e:.2f}% | {d:+.2f} |")
    resumo.append("\nArquivos: `D_curva_2t.csv`, `D_curva_1t.csv` (minuto a minuto), `D_janelas_10min_2t.csv`\n")


def main():
    bu2t, oficial, pasta_bweb, saida = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    saida.mkdir(parents=True, exist_ok=True)
    print("lendo 1º turno (bweb)...", flush=True)
    s1 = carregar_1t(pasta_bweb, saida / "secoes_1t_presidente.csv")
    print("lendo 2º turno (BUs)...", flush=True)
    s2 = carregar_2t(bu2t)
    resumo = ["# Relatório — Presidente 2026, 1º x 2º turno\n",
              f"Seções no 1º turno (bweb): {len(s1):,} · Seções no 2º turno (BUs baixados): {len(s2):,}\n"]
    relatorio_a(s2, oficial, saida, resumo)
    prevF, prevL = relatorio_b_c(s1, s2, saida, resumo)
    relatorio_d(s1, s2, prevF, prevL, saida, resumo)
    (saida / "RESUMO.md").write_text("\n".join(resumo), encoding="utf-8")
    print(f"pronto: {saida / 'RESUMO.md'}")


if __name__ == "__main__":
    main()
