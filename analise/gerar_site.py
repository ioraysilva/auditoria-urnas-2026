#!/usr/bin/env python3
"""Gera a versão estática do painel (GitHub Pages) a partir da página do painel e dos CSVs.

A página original roda num ambiente que fornece dash.data / dash.draw / dash.calc e as cores do tema.
Aqui esses três são reimplementados em poucas linhas (lendo os CSVs de dados/), para que o mesmo
código de gráficos rode em qualquer navegador, sem servidor.

Uso: python3 -I gerar_site.py <index.html do painel> <pasta com mapa_br.js e mapa_mg.js> <pasta_csv> <saida_docs>
"""
import shutil
import sys
from pathlib import Path

CABECA = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Auditoria 2º turno 2026</title>
<meta name="description" content="Boletins de urna do TSE, 2º turno presidencial de 2026: soma, recontagem pelo RDV, comparação com o 1º turno e curva da apuração.">
<style>
  :root {
    --font-anthropic-sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    --font-anthropic-serif: Georgia, "Times New Roman", serif;
    --cds-font-size-title: 2rem; --cds-font-size-heading: 1.35rem; --cds-font-size-body: 1rem; --cds-font-size-caption: .85rem;
    --cds-font-weight-medium: 600;
    --cds-gap-xs: .25rem; --cds-gap-sm: .5rem; --cds-gap-md: 1rem; --cds-gap-lg: 1.5rem; --cds-gap-xl: 2.5rem;
    --cds-pad-xs: .25rem; --cds-pad-sm: .5rem; --cds-pad-lg: 1.25rem; --cds-radius: 8px; --cds-dur-slow: .3s;
    --color-bg: #f6f5f1; --color-panel: #ffffff; --color-fg: #1f1e1c; --color-fg-muted: #6b6862;
    --color-border-line: #e2dfd8; --color-ok: #1a7f4b; --color-bad: #c0392b; --color-warn: #b7791f;
    --cds-border: #d6d3cc; --cds-surface-popover: #ffffff; --cds-shadow-popover: 0 4px 16px rgba(0,0,0,.12);
    --cds-text-secondary: #6b6862; --cds-chart-axis: #b9b5ad; --cds-chart-grid: #ece9e2; --cds-chart-reference: #8a867e;
    --cds-chart-status-critical: #c0392b;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --color-bg: #1b1a18; --color-panel: #252421; --color-fg: #ecebe8; --color-fg-muted: #a5a29b;
      --color-border-line: #3a3834; --color-ok: #4cc38a; --color-bad: #f0715f; --color-warn: #e0a64a;
      --cds-border: #45423d; --cds-surface-popover: #2c2b28; --cds-shadow-popover: 0 4px 16px rgba(0,0,0,.5);
      --cds-text-secondary: #a5a29b; --cds-chart-axis: #5a5751; --cds-chart-grid: #34322e; --cds-chart-reference: #8f8b83;
    }
  }
  :root[data-theme="dark"] {
    --color-bg: #1b1a18; --color-panel: #252421; --color-fg: #ecebe8; --color-fg-muted: #a5a29b;
    --color-border-line: #3a3834; --color-ok: #4cc38a; --color-bad: #f0715f; --color-warn: #e0a64a;
    --cds-border: #45423d; --cds-surface-popover: #2c2b28; --cds-text-secondary: #a5a29b;
    --cds-chart-axis: #5a5751; --cds-chart-grid: #34322e; --cds-chart-reference: #8f8b83;
  }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 2rem 16px 4rem; background: var(--color-bg); color: var(--color-fg); font-family: var(--font-anthropic-sans); }
  a { color: inherit; }
  .lx code { font-size: .85em; word-break: break-all; }
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>
// Substitui o ambiente do painel: dados vêm de dados/<nome>.csv
(() => {
  const DATASETS = __DATASETS__;
  const store = {}, calcs = {}, draws = {};
  let pronto = false;
  const rodar = (nome) => {
    const fn = draws[nome];
    if (!fn || !pronto) return;
    document.querySelectorAll(`[data-draw="${nome}"]`).forEach((el) => { try { fn(el); } catch (e) { console.error(nome, e); } });
  };
  window.dash = {
    data: (nome) => {
      if (nome in store) return {status: 'ok', data: store[nome]};
      const c = calcs[nome];
      if (c && c.inputs.every((i) => i in store)) { store[nome] = c.fn(...c.inputs.map((i) => store[i])); return {status: 'ok', data: store[nome]}; }
      return {status: pronto ? 'error' : 'loading', data: []};
    },
    calc: (nome, def) => { calcs[nome] = def; },
    draw: (nome, fn) => { if (fn) draws[nome] = fn; rodar(nome); },
  };
  Promise.all(DATASETS.map((n) => fetch(`dados/${n}.csv`).then((r) => r.text()).then((t) => { store[n] = d3.csvParse(t, d3.autoType); })))
    .then(() => { pronto = true; Object.keys(draws).forEach(rodar); })
    .catch((e) => { document.body.insertAdjacentHTML('afterbegin', `<p style="color:#c0392b">Erro ao carregar os dados: ${e}</p>`); });
  let w = window.innerWidth;
  window.addEventListener('resize', () => { if (Math.abs(window.innerWidth - w) > 40) { w = window.innerWidth; Object.keys(draws).forEach(rodar); } });
})();
</script>
"""

RODAPE = """
<div class="lx page" style="margin-top:3rem">
  <section class="sec" id="dados">
    <h2>Dados e como conferir</h2>
    <p>Todos os números desta página vêm dos CSVs em <a href="dados/">dados/</a>, calculados pelos scripts da pasta <code>analise/</code> do repositório a partir dos arquivos originais do TSE. Os arquivos de urna (boletim, RDV, logs) estão nos <i>Releases</i> do repositório, com o SHA-256 e o SHA-512 de cada um no manifesto. Qualquer pessoa pode baixar os mesmos arquivos do TSE, comparar os hashes e rodar os scripts para chegar aos mesmos números.</p>
    <p class="muted">Análise independente. Não é publicação do TSE nem de partido ou candidato.</p>
  </section>
</div>
</body>
</html>
"""


def main():
    pagina, mapas, csvs, saida = map(Path, sys.argv[1:5])
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "dados").mkdir(exist_ok=True)
    nomes = sorted(p.stem for p in csvs.glob("*.csv"))
    for n in nomes:
        shutil.copy2(csvs / f"{n}.csv", saida / "dados" / f"{n}.csv")
    for m in ("mapa_br.js", "mapa_mg.js"):
        shutil.copy2(mapas / m, saida / m)
    corpo = pagina.read_text(encoding="utf-8").replace('<meta name="dash-one-writer">\n', "")
    cabeca = CABECA.replace("__DATASETS__", "[" + ", ".join(f"'{n}'" for n in nomes) + "]")
    (saida / "index.html").write_text(cabeca + "</head>\n<body>\n" + corpo + RODAPE, encoding="utf-8")
    (saida / ".nojekyll").write_text("", encoding="utf-8")
    print(saida / "index.html", len(nomes), "conjuntos de dados")


if __name__ == "__main__":
    main()
