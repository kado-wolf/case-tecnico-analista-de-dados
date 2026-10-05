# Case técnico - Analista de Dados Sr

Análise de retenção e churn de uma carteira de clientes de uma empresa (fictícia) do setor jurídico. O ponto de partida foi um arquivo com contratos e planos, e o objetivo era entender a base, tratar os problemas de qualidade, definir KPIs, explicar o churn e propor uma segmentação para uma campanha de reativação.

Todos os dados são fictícios.

## Estrutura do repositório

```
contexto/       enunciado do case
dados/          arquivo original (xlsx) recebido
sql/
  bronze/       criação das tabelas bronze a partir do Google Sheets
  silver/       views tratadas (contratos e planos)
  analises/     consultas da segmentação para reativação
notebooks/      validação exploratória da base (pandas)
modelo/         modelo de risco de churn e automação de alertas (python)
docs/           documentação de cada etapa
apresentacao/   apresentação final do case
```

## Como os dados foram organizados

O arquivo do case foi para o Google Sheets e de lá para o BigQuery, em três camadas:

- **bronze**: cópia da planilha com a data de carga. Se alguém mexer na planilha, o que já foi carregado não muda.
- **silver**: views com o tratamento (tipagem, CPF corrigido, flags de qualidade e campos calculados como tempo de vida).
- **gold**: o que vai para o negócio. Score de risco de churn (`gold.score_churn`) e segmentação de reativação (`gold.vw_base_reativacao` e `gold.vw_segmentacao_reativacao`).

Como silver e gold são views, basta recarregar a bronze para tudo se atualizar.

## Documentação

- [docs/qualidade.md](docs/qualidade.md): validações feitas, problemas encontrados e como cada um foi tratado
- [docs/kpis.md](docs/kpis.md): indicadores escolhidos e como cada um é calculado
- [docs/modelo_churn.md](docs/modelo_churn.md): como funciona o modelo de risco e o alerta semanal
- [docs/segmentacao.md](docs/segmentacao.md): lógica da segmentação para a campanha de reativação

## Como rodar

Precisa de Python 3.13 e de uma conta de serviço do Google Cloud com acesso ao BigQuery. A chave fica em `credenciais/chave.json`, que não vai para o repositório.

```
pip install -r requirements.txt
```

Ordem de execução:

1. `sql/bronze/bronze.sql` no BigQuery (cria as tabelas bronze a partir das tabelas externas do Sheets)
2. `sql/silver/vw_planos.sql` e `sql/silver/vw_contratos.sql`
3. `python modelo/modelo_churn.py` (gera o score e grava em `gold.score_churn`)
4. `sql/analises/segmentacao_reativacao.sql` (cria as views da segmentação e roda as análises)
5. `python modelo/alerta_churn.py` (roda o modelo e monta o alerta para o time)

Os resultados locais ficam em `saidas/`, que também não é versionada.

## Principais resultados

- A carteira tem 428 contratos vigentes e R$ 200,9 mil de MRR. A inadimplência está em 15,2% dos contratos vigentes.
- O churn mensal médio do 3º trimestre de 2026 foi de 3,6%, o mais alto desde 2023 (média dos 10 trimestres anteriores: 2,5%).
- O tempo de casa é o que mais explica o cancelamento: 63% dos cancelamentos acontecem antes de 12 meses. Plano, periodicidade e UF quase não mudam a taxa.
- O modelo de risco, testado com dados do passado, separou bem os grupos: 24% dos contratos de risco alto cancelaram, contra 1% dos de risco baixo.
- Para a reativação, são 322 clientes perdidos e R$ 146,8 mil de MRR potencial. Business e Enterprise são 36% desses clientes e 72% do MRR.

## Limitações

- O MRR usado é o preço de tabela do plano. A base não traz o valor efetivamente pago.
- Não há dados de uso do produto, que costumam ser o melhor sinal de churn.
- `cupons_total` é um valor acumulado, sem data de uso.
- A base não tem contratos iniciados depois de 19/07/2026, mas tem cancelamentos até setembro. Isso afeta os números de volume dos últimos meses.
