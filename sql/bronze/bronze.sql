-- Criando as tabelas clientes e planos a partir das tabelas "ext".
-- isso foi feito porque as tabelas "ext" lêem o dado no sheets, caso algum dado de lá mudasse também mudaria as nossas tabelas ext. 
-- Vamos criar duas tabelas novas com a fotografia do dia atual, assim garantimos o uso do dado legítimo.



create table bronze.clientes as (

  select
    *,
    current_timestamp() as carregado_em
  from
    bronze.ext_clientes

)

create table bronze.planos as ( 

  select
    *,
    current_timestamp() as carregado_em
  from
    bronze.ext_planos

)

