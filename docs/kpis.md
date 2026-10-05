# KPIs

Indicadores que escolhi para acompanhar a carteira. Os valores são de outubro de 2026, com dados até setembro.

## Definições

| Indicador | Como é calculado | Valor atual |
|---|---|---|
| Contratos vigentes | Contratos iniciados até a data e sem cancelamento até ela (status Ativo ou Inadimplente) | 428 |
| MRR vigente | Soma da mensalidade de tabela dos contratos vigentes | R$ 200,9 mil |
| Churn mensal | Cancelamentos do mês ÷ contratos vigentes no início do mês | 2,9% (média de 12 meses) |
| MRR perdido | Mensalidade dos contratos cancelados no período | R$ 69,7 mil nos últimos 12 meses |
| Inadimplência | Contratos inadimplentes ÷ contratos vigentes | 15,2% (R$ 31,0 mil de MRR) |
| Tempo de vida | Meses entre o início e o cancelamento | 10,8 meses em média, mediana de 8 |

## Por que esses

A taxa de churn mensal é o principal. Ela mede a velocidade de perda e não depende de quantos contratos entraram, o que importa aqui: a base não tem contratos novos depois de 19/07/2026, então os números de volume (vigentes e MRR) caem nos últimos meses em parte por causa do corte dos dados.

MRR vigente e MRR perdido mostram o impacto financeiro. Inadimplência entra porque é receita em risco que ainda dá para recuperar antes de virar cancelamento. Tempo de vida mostra em que momento o cliente sai, e foi o que mais ajudou a explicar o churn.

## O que os números mostram

- A carteira cresceu até junho de 2026 (467 contratos) e recuou para 428 em setembro.
- As entradas ficam em torno de 190 contratos por ano. Os cancelamentos foram de 39 em 2021 para 123 em 2025. Em 2021 entravam 4,9 contratos para cada cancelamento, em 2025 entrou 1,5.
- O churn mensal do 3º trimestre de 2026 ficou em 3,6%, o maior desde 2023.
- Concorrência é o principal motivo de cancelamento: 33% dos casos e R$ 84,2 mil de MRR perdido.
- 63% dos cancelamentos acontecem antes de 12 meses de contrato.
- Plano e periodicidade quase não mudam a taxa de cancelamento (diferença de 6 a 7 p.p. entre o melhor e o pior grupo).

## Atualização

Os indicadores saem das views da silver, que se atualizam junto com a bronze. A proposta é agendar a recarga da bronze no BigQuery e manter um painel conectado direto nas views, além do alerta semanal descrito em [modelo_churn.md](modelo_churn.md).
