# Modelo de risco de churn

Código em [modelo/modelo_churn.py](../modelo/modelo_churn.py).

O modelo responde: qual a chance de um contrato ativo ser cancelado nos próximos 6 meses?

## Como funciona

Não usei um algoritmo de machine learning. O modelo é uma tabela de taxas históricas, montada só com pandas e numpy:

1. Para cada mês do histórico, pego os contratos que estavam vigentes naquela data (uma "fotografia").
2. Em cada fotografia, marco quem cancelou nos 6 meses seguintes.
3. Agrupo todas as fotografias por perfil (faixa de tempo de casa + usou cupom ou não) e calculo a taxa de cancelamento de cada perfil.
4. Os contratos vigentes hoje recebem a taxa do seu perfil.
5. Inadimplentes vão direto para risco alto, como regra de negócio.

Os níveis são: alto a partir de 15%, médio a partir de 8% e baixo abaixo disso.

## Por que essas variáveis

Testei plano, periodicidade, UF, região e uso de cupom olhando a taxa de cancelamento nos 6 meses seguintes. Plano, periodicidade e UF praticamente não mudam a taxa. O tempo de casa separa bem:

| Tempo de casa | Chance de cancelar nos 6 meses seguintes |
|---|---|
| 0 a 3 meses | 22,0% |
| 3 a 6 meses | 19,2% |
| 6 a 12 meses | 16,1% |
| 12 a 24 meses | 14,5% |
| 24 a 36 meses | 8,4% |
| 36 meses ou mais | 1,3% |

Quem usou cupom cancela um pouco menos em todas as faixas.

## Por que um modelo simples

Com 1.000 contratos e só duas variáveis com sinal, um modelo mais complexo não teria muito o que aprender. Preferi algo que o time de negócio consegue entender e auditar: dá para abrir a tabela de taxas e ver de onde vem cada número. Se no futuro tivermos dados de uso do produto, faz sentido evoluir para uma regressão logística.

## Validação

Para saber se funciona, simulei o passado: voltei para abril de 2026, treinei o modelo só com os dados que existiam até ali, classifiquei os contratos vigentes naquela data e comparei com quem realmente cancelou até outubro.

| Nível previsto | Contratos | Chance prevista | Cancelaram de fato |
|---|---|---|---|
| Alto | 179 | 17% | 24% |
| Médio | 100 | 12% | 16% |
| Baixo | 179 | 3% | 1% |

O modelo ordena bem o risco, mas o valor exato é aproximado. Por isso o uso é por nível e não pela probabilidade. Essa validação roda toda vez que o script é executado.

## Resultado atual

| Nível | Contratos | MRR |
|---|---|---|
| Alto | 164 | R$ 74,9 mil |
| Médio | 87 | R$ 34,6 mil |
| Baixo | 177 | R$ 91,4 mil |

## Como rodar

```
python modelo/modelo_churn.py
```

O script lê as views da silver, valida, treina, pontua os contratos vigentes e grava o resultado em `gold.score_churn` e em `saidas/score_churn.csv`. Como o treino é refeito a cada execução, contratos e cancelamentos novos entram no modelo automaticamente.

## Alerta para o time

Código em [modelo/alerta_churn.py](../modelo/alerta_churn.py).

A cada execução, o script roda o modelo e monta um e-mail com três listas:

- **Entraram em churn**: contratos cancelados nos últimos 30 dias
- **Entraram em risco alto**: contratos em risco alto que não estavam na execução anterior
- **Novos inadimplentes**: contratos que passaram a ficar inadimplentes desde a execução anterior

Para saber o que mudou, o script guarda o estado de cada execução em `saidas/alertas/estado_anterior.csv`. Na primeira execução não existe estado anterior, então todos os contratos em risco alto aparecem como novos.

O envio usa SMTP e é configurado por variáveis de ambiente (`ALERTA_DESTINATARIOS`, `SMTP_SERVIDOR`, `SMTP_PORTA`, `SMTP_USUARIO`, `SMTP_SENHA`). Sem elas, o e-mail é salvo em html em `saidas/alertas/` para conferência.

Para rodar toda segunda às 8h no Windows:

```
schtasks /create /tn "AlertaChurn" /sc weekly /d MON /st 08:00 /tr "python C:\caminho\do\projeto\modelo\alerta_churn.py"
```

## Limitações

- `cupons_total` é o acumulado de hoje. Na fotografia de um mês passado, o modelo enxerga cupons que talvez tenham sido usados depois.
- A inadimplência entra só como regra, porque a base guarda o status de hoje e não o histórico.
- Sem dados de uso do produto, o modelo não consegue diferenciar dois clientes com o mesmo tempo de casa.
