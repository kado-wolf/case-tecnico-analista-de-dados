# Segmentação para reativação

Consultas em [sql/analises/segmentacao_reativacao.sql](../sql/analises/segmentacao_reativacao.sql).

A área de CX vai fazer uma campanha para reativar clientes cancelados e não consegue falar com todos. A segmentação define quem priorizar e como abordar cada grupo.

## Quem entra na base

A campanha é por cliente (CPF), não por contrato, para ninguém receber dois contatos. Entra na base o CPF cujo contrato mais recente está cancelado e que não tem nenhum contrato em aberto. Quem cancelou um plano mas mantém outro ativo ainda é cliente: é caso de upsell, não de reativação.

Para cada cliente vale o plano e o motivo do último contrato cancelado.

Resultado: **322 clientes perdidos, com R$ 146,8 mil de MRR potencial.**

## O que os dados mostram

**Cliente cancelado volta.** Para cada contrato cancelado, procurei um contrato novo do mesmo CPF depois do cancelamento:

| Janela | Voltaram |
|---|---|
| até 6 meses | 9% |
| até 12 meses | 16% |
| até 24 meses | 28% |
| até 36 meses | 43% |
| até 48 meses | 53% |

Em cada janela só entram cancelamentos com tempo suficiente de observação. A curva não achata, então não excluí ninguém pela data do cancelamento. A recência entra só como desempate.

**O motivo muda pouco a chance de voltar.** Em 12 meses: "Outro" 24%, "Migração" 16%, "Preço" 15%, "Concorrentes" 14% e "Produto" 13%. No longo prazo, "Preço" é o que menos volta (34%).

**O dinheiro está concentrado.** Business e Enterprise são 36% dos clientes perdidos e 72% do MRR potencial. Um cliente Enterprise vale 12 clientes Start.

## Segmentos

Cada cliente cai em um segmento só, avaliado nesta ordem:

| # | Segmento | Critério | Clientes | MRR potencial | Abordagem |
|---|---|---|---|---|---|
| 1 | Alto valor | Plano Business ou Enterprise (MRR a partir de R$ 600) | 116 | R$ 105,0 mil | CS consultivo 1:1 |
| 2 | Recuperável | MRR de R$ 200 a R$ 300 e motivo "Outro" ou "Concorrentes" | 69 | R$ 17,3 mil | Contato ativo com comparativo frente à concorrência |
| 3 | Sensível a preço | Motivo "Preço" e MRR abaixo de R$ 600 | 34 | R$ 7,0 mil | E-mail com oferta de desconto ou cupom |
| 4 | Nutrição | Demais casos (plano Start, motivo "Produto" ou "Migração") | 103 | R$ 17,5 mil | Régua automática de e-mail com novidades |

O raciocínio:

- **Segmento 1**: o contato humano é o recurso mais caro e mais limitado do time, então vai para onde está o dinheiro. Com 116 contatos o time cobre 72% do MRR em jogo.
- **Segmento 2**: "Outro" é o motivo que mais volta em 12 meses e "Concorrentes" é o maior volume. São motivos que dá para contornar com argumento de valor.
- **Segmento 3**: quem saiu por preço é quem menos volta sozinho. Sem incentivo, tende a não voltar.
- **Segmento 4**: menor valor por cliente ou motivo que depende de mudança no produto. Vai para um canal de custo quase zero.

Dentro de cada segmento a ordem de contato é pelo MRR esperado (MRR do plano × chance de retorno em 12 meses do motivo) e, no empate, pelo cancelamento mais recente.

## Como usar

As consultas 1 e 5 do arquivo criam as views `gold.vw_base_reativacao` e `gold.vw_segmentacao_reativacao`. A consulta 7 gera a lista ordenada da campanha: se o time tem capacidade para N contatos, é só seguir a lista de cima para baixo. Os segmentos 3 e 4 podem ser disparados inteiros, porque são por e-mail.

Como tudo é calculado a partir da silver, inclusive as taxas de retorno por motivo, a segmentação se atualiza junto com a base.
