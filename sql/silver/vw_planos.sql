-- View de planos da camada silver.
-- Tratamento: tipagem das colunas (na bronze tudo chega como texto) e padronização dos nomes.

create or replace view silver.vw_planos as (

  select
    safe_cast(ID as int64)                      as id_plano,
    trim(nome_plano)                            as nome_plano,
    split(trim(nome_plano), ' ')[safe_offset(0)] as linha_produto,
    safe_cast(mrr_mensal as numeric)            as mrr_mensal,
    safe_cast(total_valor_contrato as numeric)  as valor_contrato_anual,
    carregado_em
  from
    bronze.planos

)
