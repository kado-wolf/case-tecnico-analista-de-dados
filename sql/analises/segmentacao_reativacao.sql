-- =====================================================================================================
-- Segmentação para a campanha de reativação de clientes cancelados
-- =====================================================================================================
-- Pergunta: a liderança de CX não vai conseguir abordar todos os cancelados. Quem priorizar e como abordar?
--
-- Lógica geral:
--   1. Definir quem é "cliente perdido" (base elegível).
--   2. Usar o histórico para medir a chance de um cancelado voltar (por motivo de cancelamento e por tempo).
--   3. Combinar valor (MRR do plano) com chance de retorno = valor esperado da reativação.
--   4. Separar em segmentos com abordagens e custos diferentes, do mais valioso para o menos.
--
-- As consultas 1 e 5 criam views na camada gold. As demais são consultas de análise.
-- Tudo é calculado a partir da silver, então os números se atualizam junto com a base.
-- =====================================================================================================


-- -----------------------------------------------------------------------------------------------------
-- 1. Base elegível: clientes perdidos
-- -----------------------------------------------------------------------------------------------------

create or replace view gold.vw_base_reativacao as (

  with contratos as (

    select
      c.*,
      p.nome_plano,
      p.linha_produto,
      p.mrr_mensal
    from
      silver.vw_contratos c
    join
      silver.vw_planos p
        on c.id_plano = p.id_plano

  ),

  resumo_cpf as (

    select
      cpf,
      count(*)                                  as qtd_contratos_historico,
      countif(flag_em_aberto)                   as qtd_contratos_em_aberto,
      sum(cupons_total)                         as cupons_total_historico
    from
      contratos
    group by
      cpf

  ),

  ultimo_contrato as (

    select
      *
    from
      contratos
    qualify
      row_number() over (partition by cpf order by data_inicio desc, id_contrato desc) = 1

  )

  select
    u.cpf,
    u.uf,
    u.id_contrato                                                       as id_ultimo_contrato,
    u.nome_plano,
    u.linha_produto,
    u.mrr_mensal,
    u.periodicidade,
    u.tipo_cancelamento,
    u.data_inicio,
    u.data_cancelamento,
    u.tempo_vida_meses,
    date_diff(current_date('America/Sao_Paulo'), u.data_cancelamento, month) as meses_desde_cancelamento,
    r.cupons_total_historico > 0                                        as usou_cupom,
    r.qtd_contratos_historico
  from
    ultimo_contrato u
  join
    resumo_cpf r
      on u.cpf = r.cpf
  where
    u.flag_cancelado
    and r.qtd_contratos_em_aberto = 0

);

-- tamanho da base elegível
select
  count(*)                 as clientes_perdidos,
  sum(mrr_mensal)          as mrr_potencial
from
  gold.vw_base_reativacao;


-- -----------------------------------------------------------------------------------------------------
-- 2. Evidência: clientes cancelados voltam? Em quanto tempo?
-- -----------------------------------------------------------------------------------------------------

with cancelados as (

  select
    *
  from
    silver.vw_contratos
  where
    flag_cancelado

),

retorno as (

  select
    a.id_contrato,
    date_diff(current_date('America/Sao_Paulo'), a.data_cancelamento, month) as meses_observados,
    min(date_diff(b.data_inicio, a.data_cancelamento, month))               as meses_ate_voltar
  from
    cancelados a
  left join
    silver.vw_contratos b
      on  a.cpf = b.cpf
      and b.id_contrato != a.id_contrato
      and b.data_inicio >= a.data_cancelamento
  group by
    1, 2

)

select
  janela_meses,
  count(*)                                                    as cancelamentos_observados,
  round(avg(if(meses_ate_voltar < janela_meses, 1, 0)), 3)    as pct_voltou_na_janela
from
  retorno,
  unnest([6, 12, 18, 24, 36, 48]) as janela_meses
where
  meses_observados >= janela_meses
group by
  janela_meses
order by
  janela_meses;


-- -----------------------------------------------------------------------------------------------------
-- 3. Evidência: a chance de voltar muda conforme o motivo do cancelamento?
-- -----------------------------------------------------------------------------------------------------

with cancelados as (

  select
    *
  from
    silver.vw_contratos
  where
    flag_cancelado

),

retorno as (

  select
    a.id_contrato,
    a.tipo_cancelamento,
    date_diff(current_date('America/Sao_Paulo'), a.data_cancelamento, month) as meses_observados,
    min(date_diff(b.data_inicio, a.data_cancelamento, month))               as meses_ate_voltar
  from
    cancelados a
  left join
    silver.vw_contratos b
      on  a.cpf = b.cpf
      and b.id_contrato != a.id_contrato
      and b.data_inicio >= a.data_cancelamento
  group by
    1, 2, 3

)

select
  tipo_cancelamento,
  count(*)                                           as cancelamentos_observados,
  round(avg(if(meses_ate_voltar < 12, 1, 0)), 3)     as pct_voltou_12_meses,
  round(avg(if(meses_ate_voltar is not null, 1, 0)), 3) as pct_voltou_alguma_vez
from
  retorno
where
  meses_observados >= 12
group by
  tipo_cancelamento
order by
  pct_voltou_12_meses desc;


-- -----------------------------------------------------------------------------------------------------
-- 4. Evidência: onde está o dinheiro?
-- -----------------------------------------------------------------------------------------------------

select
  nome_plano,
  mrr_mensal,
  count(*)                                                        as clientes,
  round(count(*) / sum(count(*)) over (), 3)                      as pct_clientes,
  sum(mrr_mensal)                                                 as mrr_potencial,
  round(sum(mrr_mensal) / sum(sum(mrr_mensal)) over (), 3)        as pct_mrr_potencial
from
  gold.vw_base_reativacao
group by
  nome_plano,
  mrr_mensal
order by
  mrr_mensal desc;


-- -----------------------------------------------------------------------------------------------------
-- 5. Segmentação
-- -----------------------------------------------------------------------------------------------------
-- Cada cliente cai em um único segmento, avaliado na ordem abaixo:
--
--   1 - Alto valor | MRR >= R$ 600 (Business e Enterprise)
--       Por quê: poucos clientes concentram a maior parte do MRR potencial (consulta 4).
--       Abordagem: contato consultivo 1:1 pelo CS, com diagnóstico do motivo e proposta personalizada.
--
--   2 - Recuperável | MRR entre R$ 200 e R$ 300 e motivo "Outro" ou "Concorrentes"
--       Por quê: são os motivos com maior retorno natural (consulta 3). "Outro" volta mais rápido e
--       "Concorrentes" é o maior volume e o segundo que mais volta no longo prazo (~44%). O motivo é contornável com argumento de valor.
--       Abordagem: contato ativo (ligação/WhatsApp) com comparativo frente à concorrência.
--
--   3 - Sensível a preço | MRR abaixo de R$ 600 e motivo "Preço"
--       Por quê: é o motivo com menor retorno no longo prazo (~34%) e, sem incentivo, tende a não voltar.
--       Abordagem: oferta com desconto ou cupom por e-mail. Usar o histórico de cupom para calibrar a oferta.
--
--   4 - Nutrição | todos os demais (plano Start, motivo "Produto" ou "Migração")
--       Por quê: menor valor por cliente ou motivo que depende de mudança no produto.
--       Abordagem: régua automática de e-mail com novidades do produto. Custo quase zero.
--
-- Valor esperado = MRR do plano x taxa de retorno em 12 meses do motivo (calculada como na consulta 3).
-- Dentro de cada segmento, a ordem de abordagem é: maior valor esperado e, no empate, cancelamento mais recente.

create or replace view gold.vw_segmentacao_reativacao as (

  with cancelados as (

    select
      *
    from
      silver.vw_contratos
    where
      flag_cancelado

  ),

  retorno as (

    select
      a.id_contrato,
      a.tipo_cancelamento,
      date_diff(current_date('America/Sao_Paulo'), a.data_cancelamento, month) as meses_observados,
      min(date_diff(b.data_inicio, a.data_cancelamento, month))               as meses_ate_voltar
    from
      cancelados a
    left join
      silver.vw_contratos b
        on  a.cpf = b.cpf
        and b.id_contrato != a.id_contrato
        and b.data_inicio >= a.data_cancelamento
    group by
      1, 2, 3

  ),

  taxa_retorno_motivo as (

    select
      tipo_cancelamento,
      avg(if(meses_ate_voltar < 12, 1, 0)) as taxa_retorno_12m
    from
      retorno
    where
      meses_observados >= 12
    group by
      tipo_cancelamento

  ),

  segmentos as (

    select
      b.*,
      t.taxa_retorno_12m,
      round(b.mrr_mensal * t.taxa_retorno_12m, 2) as mrr_esperado,
      case
        when b.mrr_mensal >= 600
          then '1 - Alto valor'
        when b.mrr_mensal >= 200 and b.tipo_cancelamento in ('Outro', 'Concorrentes')
          then '2 - Recuperável'
        when b.tipo_cancelamento = 'Preço'
          then '3 - Sensível a preço'
        else
          '4 - Nutrição'
      end as segmento
    from
      gold.vw_base_reativacao b
    left join
      taxa_retorno_motivo t
        on b.tipo_cancelamento = t.tipo_cancelamento

  )

  select
    *,
    case segmento
      when '1 - Alto valor'       then 'CS consultivo 1:1'
      when '2 - Recuperável'      then 'Contato ativo + comparativo com concorrência'
      when '3 - Sensível a preço' then 'E-mail com oferta de desconto/cupom'
      else                             'Régua automática de e-mail (novidades)'
    end as abordagem,
    row_number() over (
      partition by segmento
      order by mrr_esperado desc, meses_desde_cancelamento asc
    ) as prioridade_no_segmento
  from
    segmentos

);


-- -----------------------------------------------------------------------------------------------------
-- 6. Resumo por segmento (o que vai para a liderança)
-- -----------------------------------------------------------------------------------------------------


select
  segmento,
  abordagem,
  count(*)                                                     as clientes,
  sum(mrr_mensal)                                              as mrr_potencial,
  round(sum(mrr_esperado), 2)                                  as mrr_esperado,
  round(sum(mrr_mensal) / sum(sum(mrr_mensal)) over (), 3)     as pct_mrr_potencial,
  round(avg(meses_desde_cancelamento), 1)                      as media_meses_desde_cancelamento
from
  gold.vw_segmentacao_reativacao
group by
  segmento,
  abordagem
order by
  segmento;


-- -----------------------------------------------------------------------------------------------------
-- 7. Lista da campanha
-- -----------------------------------------------------------------------------------------------------

select
  segmento,
  prioridade_no_segmento,
  abordagem,
  cpf,
  uf,
  nome_plano,
  mrr_mensal,
  tipo_cancelamento,
  data_cancelamento,
  meses_desde_cancelamento,
  tempo_vida_meses,
  usou_cupom,
  mrr_esperado
from
  gold.vw_segmentacao_reativacao
order by
  segmento,
  prioridade_no_segmento
limit 100;
