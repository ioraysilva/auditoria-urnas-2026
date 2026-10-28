#!/usr/bin/env python3
"""Cálculos e simulações dos 4 pontos (Presidente 2026, 1º x 2º turno), com os dados já baixados.

1. Diferença entre os candidatos, Brasil e por UF.
2. Mesma seção nos dois turnos: quantas inversões / quedas / zeragens aconteceriam só por acaso
   (simulação a partir do esperado pelo 1º turno de cada seção + ruído do tamanho observado).
3. Comparecimento a mais no 2º turno x votos de Lula e Flávio (associação e contrafactual).
4. Curva na ordem de recebimento: real x esperado minuto a minuto; teste de permutação das janelas
   de 10 min; e o que apareceria se alguém tivesse trocado votos em uma janela (troca injetada).

Uso: python3 -I simulacoes.py <bu_2t.csv> <pasta_bweb_1t> <pasta_relatorios>
Grava <pasta_relatorios>/simulacoes.json (usado pela página) e imprime um resumo.
"""
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from relatorio import carregar_1t, carregar_2t, mqo, pct

random.seed(2026)
N_SIM = 200


def main():
    bu2t, pasta_bweb, saida = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    print("lendo...", flush=True)
    s1 = carregar_1t(pasta_bweb, saida / "secoes_1t_presidente.csv")
    s2 = carregar_2t(bu2t)
    chaves = [k for k in s2 if k in s1]
    out = {}

    # ---------- 1. diferença entre os candidatos ----------
    por_uf = defaultdict(lambda: defaultdict(int))
    for k in chaves:
        u = por_uf[k[0]]
        for t, s in ((1, s1[k]), (2, s2[k])):
            for c in ("aptos", "comp", "L", "F", "O", "B", "N"):
                u[f"{c}{t}"] += s[c]
    br = defaultdict(int)
    for u in por_uf.values():
        for c, v in u.items():
            br[c] += v
    def resumo_uf(u):
        v1 = u["L1"] + u["F1"] + u["O1"]
        v2 = u["L2"] + u["F2"]
        return {"aptos1": u["aptos1"], "comp1": u["comp1"], "comp2": u["comp2"],
                "L1": u["L1"], "F1": u["F1"], "O1": u["O1"], "BN1": u["B1"] + u["N1"],
                "L2": u["L2"], "F2": u["F2"], "BN2": u["B2"] + u["N2"],
                "pL1": round(pct(u["L1"], v1), 2), "pF1": round(pct(u["F1"], v1), 2),
                "pL2": round(pct(u["L2"], v2), 2), "pF2": round(pct(u["F2"], v2), 2)}
    out["brasil"] = resumo_uf(br)
    out["uf"] = {uf: resumo_uf(u) for uf, u in sorted(por_uf.items())}

    # ---------- modelo do esperado (igual ao relatorio.py) ----------
    X = [[1.0, s1[k]["L"], s1[k]["F"], s1[k]["O"], s1[k]["B"] + s1[k]["N"], s2[k]["comp"] - s1[k]["comp"]] for k in chaves]
    coefF = mqo(X, [s2[k]["F"] for k in chaves])
    coefL = mqo(X, [s2[k]["L"] for k in chaves])
    prevF = [sum(a * b for a, b in zip(coefF, x)) for x in X]
    prevL = [sum(a * b for a, b in zip(coefL, x)) for x in X]
    raiz = [math.sqrt(max(s2[k]["comp"], 1)) for k in chaves]
    rF = [(s2[k]["F"] - p) / r for k, p, r in zip(chaves, prevF, raiz)]
    rL = [(s2[k]["L"] - p) / r for k, p, r in zip(chaves, prevL, raiz)]
    dpF = math.sqrt(sum(v * v for v in rF) / len(rF))
    dpL = math.sqrt(sum(v * v for v in rL) / len(rL))
    rho = sum(a * b for a, b in zip(rF, rL)) / len(rF) / dpF / dpL
    out["modelo"] = {"coefF": coefF, "coefL": coefL, "dpF": dpF, "dpL": dpL, "rho": rho}

    # ---------- 2. marcas reais x simuladas ----------
    def marcas(F1, L1, F2, L2):
        return {"inv_FL": F1 > L1 and L2 > F2, "inv_LF": L1 > F1 and F2 > L2,
                "F_zerou": F1 >= 10 and F2 == 0, "F_caiu30": F1 >= 20 and F2 < 0.7 * F1,
                "L_caiu30": L1 >= 20 and L2 < 0.7 * L1}
    real = defaultdict(int)
    for k in chaves:
        for m, v in marcas(s1[k]["F"], s1[k]["L"], s2[k]["F"], s2[k]["L"]).items():
            real[m] += v
    real["fora4"] = sum(1 for v in rF if abs(v / dpF) >= 4)
    print("simulando marcas...", flush=True)
    sims = defaultdict(list)
    base = [(s1[k]["F"], s1[k]["L"], s2[k]["comp"]) for k in chaves]
    c = math.sqrt(1 - rho * rho)
    for _ in range(N_SIM):
        cont = defaultdict(int)
        for (F1, L1, comp2), pF, pL, r in zip(base, prevF, prevL, raiz):
            g1, g2 = random.gauss(0, 1), random.gauss(0, 1)
            F2 = max(0, min(comp2, round(pF + dpF * r * g1)))
            L2 = max(0, min(comp2 - F2, round(pL + dpL * r * (rho * g1 + c * g2))))
            if F1 > L1 and L2 > F2: cont["inv_FL"] += 1
            elif L1 > F1 and F2 > L2: cont["inv_LF"] += 1
            if F1 >= 10 and F2 == 0: cont["F_zerou"] += 1
            if F1 >= 20 and F2 < 0.7 * F1: cont["F_caiu30"] += 1
            if L1 >= 20 and L2 < 0.7 * L1: cont["L_caiu30"] += 1
            if abs(g1) >= 4: cont["fora4"] += 1
        for m in ("inv_FL", "inv_LF", "F_zerou", "F_caiu30", "L_caiu30", "fora4"):
            sims[m].append(cont[m])
    def faixa(v):
        v = sorted(v)
        return {"media": sum(v) / len(v), "p2_5": v[int(0.025 * len(v))], "p97_5": v[int(0.975 * len(v)) - 1]}
    out["marcas"] = {m: {"real": real[m], **faixa(sims[m])} for m in sims}

    # Distribuição da variação de Flávio por seção (Δ% dos votos de Flávio), real x esperado
    hist = defaultdict(lambda: [0, 0])
    for k, pF in zip(chaves, prevF):
        F1 = s1[k]["F"]
        if F1 < 20:
            continue
        for i, F2 in ((0, s2[k]["F"]), (1, pF)):
            b = max(-100, min(100, math.floor(100 * (F2 - F1) / F1 / 5) * 5))
            hist[b][i] += 1
    out["hist_var_flavio"] = [[b, *hist[b]] for b in sorted(hist)]

    # ---------- 3. comparecimento ----------
    dcomp = br["comp2"] - br["comp1"]
    efeitoL, efeitoF = coefL[5] * dcomp, coefF[5] * dcomp
    margem = br["L2"] - br["F2"]
    quint = sorted(((s2[k]["comp"] - s1[k]["comp"], s2[k]["L"] - s1[k]["L"], s2[k]["F"] - s1[k]["F"]) for k in chaves))
    q = []
    for i in range(10):
        parte = quint[i * len(quint) // 10:(i + 1) * len(quint) // 10]
        q.append([sum(p[j] for p in parte) / len(parte) for j in range(3)] + [len(parte)])
    abst1 = br["aptos1"] - br["comp1"]
    abst2 = sum(s2[k]["aptos"] for k in chaves) - br["comp2"]
    out["comparecimento"] = {"delta_comp": dcomp, "abst1": abst1, "abst2": abst2, "coefL": coefL[5], "coefF": coefF[5],
                             "efeitoL": efeitoL, "efeitoF": efeitoF, "margem": margem,
                             "margem_sem_efeito": margem - (efeitoL - efeitoF), "decis": q,
                             "subiu": sum(1 for p in quint if p[0] > 0), "caiu": sum(1 for p in quint if p[0] < 0)}

    # ---------- 4. curva ----------
    hora = [s2[k]["hora"] for k in chaves]
    por_min = defaultdict(lambda: [0, 0, 0, 0.0, 0.0])
    for k, h, pF, pL in zip(chaves, hora, prevF, prevL):
        if h:
            m = por_min[h[:16]]
            m[0] += 1; m[1] += s2[k]["L"]; m[2] += s2[k]["F"]; m[3] += pL; m[4] += pF
    ac, curva = [0, 0, 0, 0.0, 0.0], []
    for h in sorted(por_min):
        m = por_min[h]
        ac = [a + b for a, b in zip(ac, m)]
        curva.append([h, ac[0], round(pct(ac[2], ac[1] + ac[2]), 3), round(pct(ac[4], ac[3] + ac[4]), 3),
                      m[0], round(pct(m[2], m[1] + m[2]), 2) if m[1] + m[2] else None,
                      round(pct(m[4], m[3] + m[4]), 2) if m[3] + m[4] else None])
    out["curva"] = curva

    # Janelas de 10 min: desvio real (F - esperado) / votos L+F da janela, x permutações dos resíduos.
    jan = [h[:15] + "0" if h else "" for h in hora]
    ids = sorted({j for j in jan if j})
    idx = {j: i for i, j in enumerate(ids)}
    w = [idx.get(j, -1) for j in jan]
    vot = [0] * len(ids)
    for k, i in zip(chaves, w):
        if i >= 0:
            vot[i] += s2[k]["L"] + s2[k]["F"]
    resF = [s2[k]["F"] - p for k, p in zip(chaves, prevF)]
    def desvios(res):
        soma = [0.0] * len(ids)
        for v, i in zip(res, w):
            if i >= 0:
                soma[i] += v
        return [100 * s / n if n else 0.0 for s, n in zip(soma, vot)]
    dreal = desvios(resF)
    ns = [0] * len(ids)
    for i in w:
        if i >= 0:
            ns[i] += 1
    grandes = [i for i in range(len(ids)) if ns[i] >= 200]
    print("permutando...", flush=True)
    # (a) resíduos embaralhados no país todo; (b) embaralhados só dentro da mesma UF
    por_uf_idx = defaultdict(list)
    for n, k in enumerate(chaves):
        por_uf_idx[k[0]].append(n)
    perm_min_a, perm_min_b, perm_dp = [], [], [[] for _ in ids]
    for t in range(N_SIM):
        r = resF[:]
        random.shuffle(r)
        d = desvios(r)
        perm_min_a.append(min(d[i] for i in grandes))
        for i in grandes:
            perm_dp[i].append(d[i])
        r = resF[:]
        for lista in por_uf_idx.values():
            sub = [r[n] for n in lista]
            random.shuffle(sub)
            for n, v in zip(lista, sub):
                r[n] = v
        d = desvios(r)
        perm_min_b.append(min(d[i] for i in grandes))
    out["janelas"] = [{"janela": ids[i], "secoes": ns[i], "votos": vot[i], "desvio": round(dreal[i], 3),
                       "p2_5": round(sorted(perm_dp[i])[int(0.025 * N_SIM)], 3) if perm_dp[i] else None,
                       "p97_5": round(sorted(perm_dp[i])[int(0.975 * N_SIM) - 1], 3) if perm_dp[i] else None}
                      for i in range(len(ids))]
    out["perm"] = {"min_real": min(dreal[i] for i in grandes), "min_pais": faixa(perm_min_a), "min_uf": faixa(perm_min_b)}

    # Troca injetada: tirar x% dos votos de Flávio e dar a Lula nas seções recebidas entre 20:30 e 21:00.
    alvo = [n for n, j in enumerate(jan) if "2026-10-25 20:30" <= j <= "2026-10-25 20:50"]
    inj = []
    for x in (0.5, 1, 2, 5):
        movidos = sum(round(s2[chaves[n]]["F"] * x / 100) for n in alvo)
        r = resF[:]
        for n in alvo:
            r[n] -= round(s2[chaves[n]]["F"] * x / 100)
        d = desvios(r)
        inj.append({"pct": x, "votos_movidos": movidos, "desvio_min": round(min(d[i] for i in grandes), 3),
                    "margem_nova": margem + 2 * movidos})
    out["injecao"] = {"secoes_alvo": len(alvo), "cenarios": inj}

    (saida / "simulacoes.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("brasil", "marcas", "comparecimento", "perm", "injecao")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
