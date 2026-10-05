"""
Modelo de risco de churn

Pergunta que o modelo responde:
    "Qual a chance deste contrato ser cancelado nos próximos 6 meses?"

Como funciona (sem machine learning, só pandas e numpy):
    1. Voltamos no tempo, mês a mês, e tiramos uma "fotografia" dos contratos que estavam ativos em cada data.
    2. Para cada fotografia, olhamos 6 meses para frente e marcamos quem cancelou.
    3. Agrupamos essas fotografias por perfil (tempo de casa + uso de cupom) e calculamos a taxa de cancelamento
       de cada perfil. Essa tabela de taxas é o "modelo".
    4. Para os contratos ativos hoje, buscamos a taxa do perfil deles na tabela. Essa é a probabilidade de churn.
    5. Contratos inadimplentes vão direto para risco Alto (regra de negócio).

Por que só tempo de casa e cupom?
    Testamos plano, periodicidade, UF e região: a taxa de cancelamento futuro é praticamente igual entre os grupos,
    ou seja, não ajudam a prever. Já o tempo de casa separa bem (contratos com até 3 meses cancelam ~7x mais que
    contratos com mais de 3 anos) e quem usa cupom cancela um pouco menos.

Por que é atualizável?
    Toda execução lê a camada silver do BigQuery e recalcula a tabela de taxas com todo o histórico disponível.
    Novos contratos e cancelamentos entram automaticamente no modelo.

Como rodar:
    python modelo/modelo_churn.py

Saídas:
    saidas/score_churn.csv          -> score de todos os contratos ativos
    saidas/tabela_risco.csv         -> a tabela de taxas por perfil (o "modelo")
    BigQuery: gold.score_churn      -> mesmo conteúdo do csv, para consumo em dashboard
"""

from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

# caminhos
PASTA_PROJETO = Path(__file__).resolve().parent.parent
CAMINHO_CHAVE = PASTA_PROJETO / "credenciais" / "chave.json"
PASTA_SAIDAS = PASTA_PROJETO / "saidas"

# tabela de destino no BigQuery
DATASET_DESTINO = "gold"
TABELA_DESTINO = "gold.score_churn"

# parâmetros do modelo
HORIZONTE_MESES = 6                                     # janela de previsão: cancelar nos próximos 6 meses
FAIXAS_MESES = [0, 3, 6, 12, 24, 36, np.inf]            # faixas de tempo de casa
NOMES_FAIXAS = ["0-3 meses", "3-6 meses", "6-12 meses", "12-24 meses", "24-36 meses", "36+ meses"]
LIMITE_ALTO = 0.15                                      # probabilidade a partir da qual o risco é Alto
LIMITE_MEDIO = 0.08                                     # probabilidade a partir da qual o risco é Médio


def carregar_contratos(client):
    """Lê os contratos da camada silver já com os dados do plano."""

    query = """
    select
        c.id_contrato,
        c.cpf,
        c.uf,
        c.periodicidade,
        c.status,
        c.data_inicio,
        c.data_cancelamento,
        c.cupons_total,
        p.nome_plano,
        p.mrr_mensal
    from
        silver.vw_contratos c
    join
        silver.vw_planos p
            on c.id_plano = p.id_plano
    """

    df = client.query(query).to_dataframe()

    # tipagem para conseguir fazer contas com datas e números
    df["data_inicio"] = pd.to_datetime(df["data_inicio"])
    df["data_cancelamento"] = pd.to_datetime(df["data_cancelamento"])
    df["cupons_total"] = df["cupons_total"].astype(float)
    df["mrr_mensal"] = df["mrr_mensal"].astype(float)

    return df


def fotografia(df, data_ref):
    """
    Retorna os contratos que estavam ativos em uma data, com o perfil de cada um naquela data.
    Ativo na data = já tinha começado e ainda não tinha sido cancelado.
    """

    ativos = df[
        (df["data_inicio"] <= data_ref)
        & (df["data_cancelamento"].isna() | (df["data_cancelamento"] > data_ref))
    ].copy()

    ativos["data_referencia"] = data_ref
    ativos["meses_de_casa"] = (data_ref - ativos["data_inicio"]).dt.days / 30.44
    ativos["faixa_tempo"] = pd.cut(ativos["meses_de_casa"], bins=FAIXAS_MESES, labels=NOMES_FAIXAS, right=False).astype(str)

    # observação: cupons_total é o acumulado de hoje, não temos o histórico de quando o cupom foi usado
    ativos["usou_cupom"] = np.where(ativos["cupons_total"] > 0, "Com cupom", "Sem cupom")

    return ativos


def montar_historico(df, ate):
    """
    Junta uma fotografia por mês, do primeiro contrato até `ate` menos o horizonte,
    e marca quem cancelou nos HORIZONTE_MESES seguintes a cada fotografia.
    Só usamos datas em que já conseguimos enxergar os 6 meses seguintes completos.
    """

    ultima_data = ate - pd.DateOffset(months=HORIZONTE_MESES)
    datas = pd.date_range(df["data_inicio"].min(), ultima_data, freq="MS")

    fotos = []
    for data_ref in datas:
        foto = fotografia(df, data_ref)
        limite = data_ref + pd.DateOffset(months=HORIZONTE_MESES)
        foto["cancelou"] = foto["data_cancelamento"] <= limite     # data vazia (NaT) resulta em False
        fotos.append(foto)

    return pd.concat(fotos, ignore_index=True)


def treinar(historico):
    """
    O "treino" é um groupby: taxa de cancelamento de cada perfil (faixa de tempo de casa + uso de cupom).
    """

    tabela = (
        historico
        .groupby(["faixa_tempo", "usou_cupom"])
        .agg(observacoes=("cancelou", "size"), cancelamentos=("cancelou", "sum"))
        .reset_index()
    )
    tabela["probabilidade_churn"] = tabela["cancelamentos"] / tabela["observacoes"]

    # ordenando as faixas do menor para o maior tempo de casa (e não em ordem alfabética)
    tabela["ordem"] = tabela["faixa_tempo"].map({nome: i for i, nome in enumerate(NOMES_FAIXAS)})
    tabela = tabela.sort_values(["ordem", "usou_cupom"]).drop(columns="ordem").reset_index(drop=True)

    return tabela


def pontuar(df, tabela, data_ref, considerar_inadimplencia=True):
    """Aplica a tabela de taxas aos contratos ativos em `data_ref` e classifica o nível de risco."""

    scores = fotografia(df, data_ref).merge(
        tabela[["faixa_tempo", "usou_cupom", "probabilidade_churn"]],
        on=["faixa_tempo", "usou_cupom"],
        how="left",
    )

    prob = scores["probabilidade_churn"]
    inadimplente = (scores["status"] == "Inadimplente") & considerar_inadimplencia

    # np.select avalia as condições na ordem: a primeira verdadeira define o resultado
    scores["nivel_risco"] = np.select(
        [inadimplente, prob >= LIMITE_ALTO, prob >= LIMITE_MEDIO],
        ["Alto", "Alto", "Médio"],
        default="Baixo",
    )

    scores["motivo_risco"] = np.select(
        [inadimplente, prob >= LIMITE_ALTO, prob >= LIMITE_MEDIO],
        [
            "Inadimplente",
            "Fase de maior risco: " + scores["faixa_tempo"] + ", " + scores["usou_cupom"].str.lower(),
            "Fase de risco moderado: " + scores["faixa_tempo"] + ", " + scores["usou_cupom"].str.lower(),
        ],
        default="",
    )

    return scores


def validar(df, hoje):
    """
    Backtest: finge que estamos 6 meses atrás, treina só com o que se sabia naquela época,
    pontua os contratos ativos naquela data e compara com quem realmente cancelou depois.
    Se o modelo funciona, a taxa real de cancelamento do nível Alto tem que ser maior que a do Baixo.
    """

    data_teste = hoje - pd.DateOffset(months=HORIZONTE_MESES)

    tabela = treinar(montar_historico(df, ate=data_teste))

    # inadimplência fica de fora: só conhecemos o status de hoje, não o de 6 meses atrás
    teste = pontuar(df, tabela, data_teste, considerar_inadimplencia=False)
    teste["cancelou"] = teste["data_cancelamento"] <= hoje

    resultado = (
        teste
        .groupby("nivel_risco")
        .agg(
            contratos=("cancelou", "size"),
            probabilidade_prevista=("probabilidade_churn", "mean"),
            taxa_real_de_churn=("cancelou", "mean"),
        )
        .reindex(["Alto", "Médio", "Baixo"])
    )

    return data_teste, resultado


def salvar(scores, tabela, client):
    """Salva os resultados em csv e sobrescreve a tabela do BigQuery."""

    PASTA_SAIDAS.mkdir(exist_ok=True)
    scores.to_csv(PASTA_SAIDAS / "score_churn.csv", index=False, encoding="utf-8-sig")
    tabela.to_csv(PASTA_SAIDAS / "tabela_risco.csv", index=False, encoding="utf-8-sig")

    dataset = bigquery.Dataset(f"{client.project}.{DATASET_DESTINO}")
    dataset.location = "US"
    client.create_dataset(dataset, exists_ok=True)

    config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    client.load_table_from_dataframe(scores, TABELA_DESTINO, job_config=config).result()


def executar(client=None, salvar_resultados=True):
    """Roda o fluxo completo: carrega, valida, treina, pontua e salva. Retorna (contratos, scores)."""

    if client is None:
        client = bigquery.Client.from_service_account_json(str(CAMINHO_CHAVE))

    hoje = pd.Timestamp.today().normalize()
    contratos = carregar_contratos(client)

    # 1. validação (backtest)
    data_teste, resultado = validar(contratos, hoje)
    print(f"Validação: contratos ativos em {data_teste.date()} x cancelamentos reais até {hoje.date()}")
    print(resultado.round(3).to_string(), "\n")

    # 2. treino com todo o histórico disponível
    tabela = treinar(montar_historico(contratos, ate=hoje))
    print("Tabela de risco (o modelo):")
    print(tabela.round(3).to_string(index=False), "\n")

    # 3. score dos contratos ativos hoje
    scores = pontuar(contratos, tabela, hoje)
    scores["data_execucao"] = hoje

    colunas = [
        "data_execucao", "id_contrato", "cpf", "uf", "nome_plano", "mrr_mensal", "periodicidade", "status",
        "data_inicio", "meses_de_casa", "faixa_tempo", "usou_cupom", "probabilidade_churn", "nivel_risco",
        "motivo_risco",
    ]
    scores = scores[colunas].sort_values("probabilidade_churn", ascending=False)
    scores["meses_de_casa"] = scores["meses_de_casa"].round(1)

    print("Contratos ativos por nível de risco:")
    print(scores.groupby("nivel_risco").agg(contratos=("id_contrato", "size"), mrr=("mrr_mensal", "sum")).to_string(), "\n")

    if salvar_resultados:
        salvar(scores, tabela, client)
        print(f"Resultados salvos em {PASTA_SAIDAS} e na tabela {TABELA_DESTINO}")

    return contratos, scores


if __name__ == "__main__":
    executar()
