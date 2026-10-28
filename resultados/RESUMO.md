# Relatório — Presidente 2026, 1º x 2º turno

Seções no 1º turno (bweb): 499,206 · Seções no 2º turno (BUs baixados): 499,205

## A. Soma dos boletins de urna x resultado oficial do TSE (Presidente, 2º turno)

- Municípios comparados: 5,757
- **Idênticos nos votos** (comparecimento, brancos, nulos, Lula e Flávio iguais): **5,757**
- **Divergentes** (soma dos BUs diferente do oficial sem ser só falta de BU): **0**
- Incompletos (algum BU não baixado: tudo menor que o oficial, nada maior): 0

| | Oficial TSE | Soma dos BUs | Diferença |
|---|---:|---:|---:|
| Seções | 499,248 | 499,205 | -43 |
| Comparecimento | 128,236,074 | 128,236,074 | +0 |
| Lula | 64,256,232 | 64,256,232 | +0 |
| Flávio | 59,826,041 | 59,826,041 | +0 |
| Brancos | 1,430,496 | 1,430,496 | +0 |
| Nulos | 2,723,305 | 2,723,305 | +0 |

Arquivo: `A_bu_vs_oficial_municipios.csv`

## B. Mesma seção no 1º e no 2º turno (Presidente)

- Seções presentes nos dois turnos: 499,205 (só no 2º: 0; só no 1º: 1 — seções agregadas/desagregadas ou BUs ainda não baixados)
- Nessas seções: Flávio 56,104,503 → 59,826,041 (+3,721,538); Lula 53,879,536 → 64,256,232 (+10,376,696)
- Modelo do esperado (votos do 2º turno explicados pelo 1º turno da mesma seção: Lula, Flávio, outros, brancos+nulos e variação de comparecimento):

| Termo | Flávio 2T | Lula 2T |
|---|---:|---:|
| constante | 1.687 | -1.790 |
| Lula 1T | -0.043 | 1.039 |
| Flávio 1T | 1.000 | -0.007 |
| outros 1T | 0.440 | 0.442 |
| brancos+nulos 1T | -0.022 | 0.636 |
| Δ comparecimento | 0.414 | 0.546 |

- Contagem de marcas (uma seção pode ter várias):
  - inversão F→L: 31,395
  - Flávio caiu >30%: 635
  - inversão L→F: 565
  - fora do esperado: 402
  - Lula caiu >30%: 75
  - Flávio zerou: 1

"Fora do esperado" = |z| ≥ 4, ou seja, a seção desvia 4 desvios-padrão do previsto pelo próprio 1º turno. Em ~500 mil seções, algumas dezenas assim são normais por acaso; centenas concentradas num lugar merecem olhar.

Arquivos: `B_urnas_1t_x_2t.csv` (todas), `B_urnas_destaques.csv` (só as marcadas, das mais negativas para Flávio)

## C. Eleitores a mais no 2º turno (comparecimento)

- Nas seções comparáveis, o comparecimento variou +2,960,241; Lula +10,376,696; Flávio +3,721,538; votos de outros candidatos no 1º turno: 9,321,993; brancos+nulos 5,969,801 → 4,153,801
- Pelo modelo acima, **cada eleitor a mais numa seção está associado a +0.55 voto para Lula e +0.41 para Flávio** (média entre seções; é associação, não prova de quem votou em quem — o voto é secreto).

| Faixa de Δ comparecimento (quintis) | Seções | Δ comp médio | Δ Lula médio | Δ Flávio médio |
|---|---:|---:|---:|---:|
| Q1 | 99,841 | -6.6 | +11.7 | +0.6 |
| Q2 | 99,841 | +2.0 | +17.4 | +5.8 |
| Q3 | 99,841 | +6.0 | +20.4 | +8.2 |
| Q4 | 99,841 | +10.1 | +23.7 | +10.1 |
| Q5 | 99,841 | +18.3 | +30.7 | +12.5 |

## D. Curva da apuração (ordem de recebimento dos BUs)

| Hora | % seções | Lula | Flávio |
|---|---:|---:|---:|
| 17:04 | 0.0% | 41.07% | 58.93% |
| 19:51 | 16.3% | 49.73% | 50.27% |
| 20:41 | 67.8% | 50.83% | 49.17% |
| 21:31 | 99.4% | 51.73% | 48.27% |
| 22:29 | 99.5% | 51.75% | 48.25% |
| 10:14 | 99.5% | 51.76% | 48.24% |
| 12:14 | 99.6% | 51.77% | 48.23% |
| 18:58 | 99.7% | 51.77% | 48.23% |
| 09:35 | 99.8% | 51.78% | 48.22% |
| 10:42 | 99.8% | 51.78% | 48.22% |
| 11:38 | 99.9% | 51.79% | 48.21% |
| 14:10 | 99.9% | 51.78% | 48.22% |
| 22:31 | 100.0% | 51.79% | 48.21% |
| 22:31 | 100.0% | 51.79% | 48.21% |

- Janelas de 10 min com ≥200 seções: 16. Diferença média entre a % real de Flávio e a % esperada para aquelas mesmas seções (pelo 1º turno delas): **+0.03 p.p.**; menor -0.25 p.p., maior +0.15 p.p.
- Se a totalização tivesse tirado votos de Flávio em certos momentos, as janelas desses momentos apareceriam com diferença bem negativa **e** a soma dos BUs não bateria com o oficial (relatório A). As oscilações da curva em si vêm de *quais* seções chegam em cada momento (região, fuso, capital x interior).

| Janelas mais desfavoráveis a Flávio | Seções | % real | % esperada | Dif. |
|---|---:|---:|---:|---:|
| 21:00 | 53,322 | 46.48% | 46.73% | -0.25 |
| 20:50 | 55,307 | 46.11% | 46.21% | -0.10 |
| 20:40 | 57,188 | 46.58% | 46.60% | -0.02 |
| 19:30 | 27,714 | 50.26% | 50.25% | +0.01 |
| 19:00 | 5,982 | 48.85% | 48.80% | +0.05 |
| 19:20 | 14,684 | 49.60% | 49.55% | +0.05 |
| 20:00 | 48,915 | 50.40% | 50.34% | +0.06 |
| 19:50 | 33,777 | 51.24% | 51.18% | +0.06 |

Arquivos: `D_curva_2t.csv`, `D_curva_1t.csv` (minuto a minuto), `D_janelas_10min_2t.csv`
