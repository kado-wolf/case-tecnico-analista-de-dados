-- View de contratos da camada silver. Cada linha representa um contrato (um CPF pode ter vários).
-- Tratamentos aplicados (validados no notebooks/validacao.ipynb):
--   1. tipagem das colunas (na bronze tudo chega como texto) e padronização dos nomes
--   2. CPF completado com zeros à esquerda até 11 dígitos (104 registros vieram sem os zeros já na origem)
--   3. flag de violação da regra "o mesmo plano não pode estar ativo simultaneamente no mesmo CPF"
--      os registros são mantidos, pois não é possível saber qual das datas está errada

create or replace view silver.vw_contratos as (

  with contratos as (

    select
      safe_cast(ID as int64)                        as id_contrato,
      api_key,
      lpad(trim(CPF), 11, '0')                      as cpf,
      length(trim(CPF)) < 11                        as flag_cpf_corrigido,
      upper(trim(UF))                               as uf,
      safe_cast(ID_PLANO as int64)                  as id_plano,
      trim(Periodicidade)                           as periodicidade,
      safe_cast(inicio_data as date)                as data_inicio,
      safe_cast(cancto_data as date)                as data_cancelamento,
      trim(tipo_cancelamento)                       as tipo_cancelamento,
      trim(status)                                  as status,
      safe_cast(cupons_total as numeric)            as cupons_total,
      carregado_em
    from
      bronze.clientes

  ),

  vigencia as (

    -- contratos sem data de cancelamento seguem vigentes, então o fim da vigência é a data atual
    select
      *,
      coalesce(data_cancelamento, current_date('America/Sao_Paulo')) as data_fim_vigencia
    from
      contratos

  ),

  sobreposicoes as (

    -- pares de contratos do mesmo CPF e mesmo plano cujos períodos se cruzam
    select distinct
      a.id_contrato
    from
      vigencia a
    join
      vigencia b
        on  a.cpf = b.cpf
        and a.id_plano = b.id_plano
        and a.id_contrato != b.id_contrato
        and a.data_inicio < b.data_fim_vigencia
        and b.data_inicio < a.data_fim_vigencia

  )

  select
    v.id_contrato,
    v.api_key,
    v.cpf,
    v.uf,
    v.id_plano,
    v.periodicidade,
    v.data_inicio,
    v.data_cancelamento,
    v.data_fim_vigencia,
    v.tipo_cancelamento,
    v.status,
    v.status = 'Cancelado'                                         as flag_cancelado,
    v.data_cancelamento is null                                    as flag_em_aberto,
    v.cupons_total,
    date_diff(v.data_fim_vigencia, v.data_inicio, day)             as tempo_vida_dias,
    date_diff(v.data_fim_vigencia, v.data_inicio, month)           as tempo_vida_meses,
    row_number() over (partition by v.cpf order by v.data_inicio, v.id_contrato) as ordem_contrato_cpf,
    count(*) over (partition by v.cpf)                             as qtd_contratos_cpf,
    v.flag_cpf_corrigido,
    s.id_contrato is not null                                      as flag_sobreposicao_mesmo_plano,
    v.carregado_em
  from
    vigencia v
  left join
    sobreposicoes s
      on v.id_contrato = s.id_contrato

)
