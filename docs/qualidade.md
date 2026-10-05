# Qualidade dos dados

As validações foram feitas em cima da camada bronze, no notebook [notebooks/validacao.ipynb](../notebooks/validacao.ipynb). O tratamento ficou nas views da silver ([sql/silver](../sql/silver)).

## O que foi validado

| Validação | Resultado |
|---|---|
| `api_key` é única por contrato? | Sim, 1.000 chaves para 1.000 contratos |
| CPFs têm 11 dígitos? | Não. 104 registros (80 CPFs) com 9 ou 10 dígitos |
| Existem linhas duplicadas? | Não |
| Nulos fora do esperado? | Não. Só `cancto_data` e `tipo_cancelamento`, que ficam vazios para contratos não cancelados |
| Data de início no futuro? | Não |
| Cancelamento antes do início? | Não |
| Motivo sem data de cancelamento, ou o contrário? | Não |
| Status coerente com a data de cancelamento? | Sim. Todo "Cancelado" tem data e motivo, "Ativo" e "Inadimplente" não têm |
| Todo `ID_PLANO` existe na tabela de planos? | Sim |
| O mesmo plano fica ativo duas vezes no mesmo CPF? | Hoje não, mas no histórico sim (11 casos) |

## Problemas encontrados e o que foi feito

**CPF sem os zeros à esquerda.** 104 registros vieram com 9 ou 10 dígitos. O problema já está no xlsx original, então não foi a carga que causou. O mais provável é a coluna ter sido tratada como número em algum momento. Como todos os valores são só dígitos e nenhum passa de 11, completei com zeros à esquerda (`lpad` na silver). Antes e depois do tratamento continuam sendo 750 CPFs distintos, ou seja, nenhum CPF virou outro. A coluna `flag_cpf_corrigido` marca os registros alterados.

**Mesmo plano ativo duas vezes no mesmo CPF.** O enunciado diz que um CPF pode ter vários contratos, mas não o mesmo plano ativo ao mesmo tempo. Olhando só os contratos em aberto hoje, a regra é respeitada. Comparando os períodos de vigência de todo o histórico, aparecem 11 pares de contratos do mesmo plano que se sobrepõem. Como não dá para saber qual das datas está errada, mantive os registros e marquei com `flag_sobreposicao_mesmo_plano`.

A comparação considera que dois contratos se sobrepõem quando cada um começa antes do outro terminar. Contrato sem cancelamento termina na data atual.

**Tudo como texto.** Na bronze, datas, valores e IDs chegam como `STRING`. Na silver tudo foi convertido com `safe_cast`, e a conferência abaixo mostra que nenhum valor virou nulo na conversão.

**Inconsistências que levei para o negócio, sem alterar o dado:**

- Dos 87 cancelamentos com motivo "Migração", só 8 têm outro contrato do mesmo CPF perto da data do cancelamento. Ou o cliente migrou para fora, ou o motivo está sendo registrado de outro jeito.
- 67 dos 111 contratos anuais cancelados duraram menos de 12 meses. Vale entender como funciona a fidelidade desses planos.
- O `total_valor_contrato` é sempre 12 vezes o `mrr_mensal`, independente da periodicidade.

## Conferência entre bronze e silver

Para garantir que o tratamento não perdeu nem alterou nada:

| Checagem | Bronze | Silver |
|---|---|---|
| Linhas | 1.000 | 1.000 |
| Soma de `cupons_total` | 426.325,04 | 426.325,04 |
| Ativo / Cancelado / Inadimplente | 363 / 572 / 65 | 363 / 572 / 65 |
| `cancto_data` vazia | 428 | 428 |
| CPFs fora de 11 dígitos | 104 | 0 |
| Contratos com plano inexistente | 0 | 0 |
| Status incoerente com a data | 0 | 0 |

A ideia é rodar essas mesmas checagens a cada nova carga, antes de atualizar painel e alertas.

## Limitações da base

- Não existe o valor efetivamente pago. O MRR usado em todas as análises é o preço de tabela do plano.
- Não há dados de uso do produto.
- `cupons_total` é um acumulado, sem a data de uso do cupom.
- Em 197 CPFs a UF muda de um contrato para outro. Pode ser mudança de endereço, mas também reforça que os dados são fictícios.
- Só 8 dos 750 CPFs têm dígito verificador válido. Não tratei isso, porque os dados são fictícios, mas numa base real seria uma validação obrigatória.
