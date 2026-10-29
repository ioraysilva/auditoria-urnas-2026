# Auditoria independente dos boletins de urna — Presidente 2026, 2º turno

Conferência pública, com dados e código abertos, do resultado do 2º turno presidencial de 25/10/2026 (Lula × Flávio) a partir dos arquivos originais publicados pelo TSE.

**Painel com todos os gráficos e mapas:** a pasta [`docs/`](docs/) é publicada pelo GitHub Pages (endereço no topo do repositório, em *About* → *Website*).

Esta análise é independente. Não é publicação do TSE, de partido ou de candidato. Qualquer pessoa pode baixar os mesmos arquivos do TSE, conferir os hashes e rodar os scripts para chegar aos mesmos números.

## O que foi verificado

| Verificação | Resultado |
|---|---|
| Soma dos boletins de urna (BU) de 499.205 seções × total oficial do TSE | Igual em **5.757 de 5.757** municípios. Lula 64.256.232, Flávio 59.826.041, brancos 1.430.496, nulos 2.723.305 |
| Recontagem voto a voto pelo RDV (registro digital do voto) × BU da mesma urna | **499.206 seções iguais, 0 diferentes.** Uma seção (CE 14176/21/136) não tem RDV publicado |
| Curva da apuração minuto a minuto (horário de recebimento de cada BU) | A variação da % de Flávio a cada minuto acompanha a esperada pelo 1º turno das urnas que chegaram (correlação 0,998) |
| Mesma seção no 1º e no 2º turno | Lula +10.376.696, Flávio +3.721.538. Pontos de atenção e seções fora do esperado listados no painel |
| Hipótese de inversão dos votos de Lula e Flávio | Incompatível com os dados: invertidos, os números contrariam o 1º turno de cada seção (correlação 0,985 publicada × −0,978 invertida) |

Os pontos de atenção (ganho de Lula maior que a "sobra" disponível em parte das seções, comparecimento que saltou em algumas seções, janelas da apuração) estão no painel com os números e as tabelas de seções para conferência individual. Os limites da análise também estão no painel: ela confere os arquivos publicados entre si; não confere se o boletim impresso afixado na seção é igual ao arquivo.

## Indícios de inconsistência

A seção em destaque "Indícios de inconsistência", logo antes dos pontos de atenção, confere, nos boletins de urna, números que circularam após a eleição. Todos conferem, alguns com pequena diferença. O que muda é a leitura quando cada grupo de urnas é comparado com ele mesmo no 1º turno:

| Alegação | Nos boletins | Comparado com o 1º turno |
|---|---|---|
| 106 seções com zero voto para Flávio | 106 (e 4 com zero para Lula) | Em 90 delas Flávio já tinha 0 a 2 votos no 1º turno |
| 100% para um candidato: 106 Lula × 4 Flávio | 106 × 4 | No 1º turno, 80 × 8 |
| 90% ou mais: 6.899 Lula × 384 Flávio | 6.899 × 384 | No 1º turno, 6.099 × 726; esperado pelo 1º turno, 8.676 × 445 |
| Urnas encerradas até 17h: Flávio 52,39%, +1,8 mi | 52,40%, +1.748.468 | Nas mesmas urnas, no 1º turno: 55,20%, +3.397.055 |
| Urnas encerradas depois das 17h: Lula +6,1 mi | +6.150.002 | Nas mesmas urnas Lula já vencia o 1º turno por 1.158.603 |
| 674.799 votantes em urnas encerradas entre 17h16 e 18h59 | 657.545 (hora local) ou 675.796 (Brasília) | Flávio −0,16 ponto do esperado |
| 1.856.306 votantes em urnas encerradas às 19h ou depois | 1.858.274 (hora local) ou 1.861.259 (Brasília) | Flávio −0,36 ponto do esperado |
| 8.632.488 votaram sem biometria (6,73%) | 8.632.488 (6,73%) | Onde há mais desses eleitores, Lula ficou 0,24 ponto **abaixo** do esperado |

Script: [`analise/conferir_alegacoes.py`](analise/conferir_alegacoes.py). Dados: `docs/dados/alegacoes.csv`, `zero_flavio.csv`, `horario.csv`, `extremos.csv`, `biometria_quintis.csv`.

## Arquivos do TSE

Os arquivos originais não cabem no repositório (vários GB) e estão nos **Releases** (`arquivos-tse-v1`), sem alteração:

| Arquivo | Conteúdo | Origem |
|---|---|---|
| `urnas_2t_<uf>.tar.gz` | Por seção: boletim de urna (`-bu.dat`, ou `-busa.dat` quando apurado pelo Sistema de Apuração), RDV (`-rdv.dat`) e o `aux.json` do TSE com o hash do pacote | `resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/` |
| `urnas_1t_<uf>.tar.gz` | O mesmo para o 1º turno, mais logs (`-log.jez`, `logsa`) e arquivos do Sistema de Apuração | `resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/` |
| `bweb_1t_<UF>_051020261403.zip` (+ `.sha512`) | Boletins de urna do 1º turno em CSV, como publicados no Portal de Dados Abertos | `dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna` |
| `SHA256SUMS` | SHA-256 de cada pacote do Release | calculado aqui |

### Como conferir os hashes

- [`manifesto/urnas_2t/`](manifesto/urnas_2t/) tem um arquivo por UF com **uma linha por arquivo de urna**: UF, município, zona, seção, nome do arquivo, tamanho, SHA-256, o hash do pacote informado pelo TSE e a situação da seção no TSE. Com essas colunas, a URL de cada arquivo no TSE é

  ```
  https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados/<uf>/<municipio>/<zona>/<secao>/<hash_pacote>/<arquivo>
  ```

  Baixe o arquivo dessa URL e compare o SHA-256 com o do manifesto:

  ```bash
  shasum -a 256 o03221df9701200010009-bu.dat
  ```

- [`manifesto/bweb_1t_sha512.csv`](manifesto/bweb_1t_sha512.csv) compara o SHA-512 publicado pelo TSE para cada `bweb` com o calculado aqui: **28 de 28 conferem**. Os `.sha512` originais do TSE estão em `manifesto/sha512_tse/`.
- O "hash do pacote TSE" é o identificador que o próprio TSE dá ao conjunto de arquivos de cada seção (está no `aux.json` e faz parte da URL). Ele não é um hash calculado por nós.

## Como reproduzir

Requer Python 3.9 ou mais novo, sem bibliotecas externas.

```bash
# 1. Baixar os arquivos de urna do 2º turno (BU e RDV), ou extrair os do Release em 2t/
python3 -I analise/baixar_bu.py --saida 2t --pleito 3221 --tipos bu,rdv
# 2. Ler os BUs para CSV
python3 -I analise/ler_bu.py 2t 2t/bu_2t.csv
# 3. Resultado oficial por município, para comparar
python3 -I analise/baixar_oficial.py 2t 2t/oficial_presidente_2t.csv
# 4. Relatório: BU x oficial, mesma seção no 1º e 2º turno (bweb do 1º turno na pasta atual)
python3 -I analise/relatorio.py 2t/bu_2t.csv 2t/oficial_presidente_2t.csv . relatorios
# 5. Recontagem pelo RDV
python3 -I analise/recontar_rdv.py 2t relatorios/recontagem_rdv_brasil.csv
# 6. Hashes de todos os arquivos
python3 -I analise/manifesto.py 2t manifesto/urnas_2t/urnas_2t
```

Cada script explica no cabeçalho o que faz e os argumentos que recebe.

## Estrutura

```
docs/        painel (GitHub Pages): index.html, mapas e dados/*.csv que alimentam cada gráfico
analise/     scripts: download, leitura do BU/RDV (ASN.1), relatório, simulações, recontagem, manifesto, site
resultados/  saídas: comparação por município e por seção, recontagem do RDV, CSVs do painel (.gz quando grandes)
manifesto/   hashes de todos os arquivos do TSE usados
scripts/     empacotamento e publicação dos Releases
```

## Observações

- A tabela histórica de 1º × 2º turno (Brasil e outros países) foi digitada de referência geral, não baixada de fonte oficial. Confira antes de citar.
- Estimativas de "para onde foi o eleitor" (regressão ecológica) mostram associação entre seções, não o voto individual, que é secreto.
- Correções e novas verificações são bem-vindas por *issue* ou *pull request*.
