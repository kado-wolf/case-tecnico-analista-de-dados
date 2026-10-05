"""
Automação de alertas de churn para o time de negócios

O que faz a cada execução:
    1. Roda o modelo de churn (modelo_churn.py), que lê os dados atualizados da camada silver.
    2. Monta três listas:
        - Entraram em churn: contratos cancelados nos últimos JANELA_DIAS dias
        - Entraram em risco alto: contratos que estão em risco Alto hoje e não estavam na execução anterior
        - Novos inadimplentes: contratos que viraram Inadimplente desde a execução anterior
    3. Envia um e-mail com as listas para o time (ou salva o e-mail em html, se o envio não estiver configurado).
    4. Guarda o estado atual para comparar na próxima execução.

Como saber o que é "novo"?
    A cada execução salvamos um csv com o status e o nível de risco de cada contrato (saidas/alertas/estado_anterior.csv).
    Na execução seguinte, comparamos o resultado atual com esse arquivo. Na primeira execução não existe estado anterior,
    então todos os contratos em risco Alto e todos os inadimplentes aparecem como novos.

Configuração do e-mail (variáveis de ambiente):
    ALERTA_DESTINATARIOS   e-mails separados por vírgula, ex: cs@empresa.com,lideranca@empresa.com
    SMTP_SERVIDOR          ex: smtp.gmail.com
    SMTP_PORTA             ex: 587
    SMTP_USUARIO           e-mail remetente
    SMTP_SENHA             senha de app do remetente
    Sem essas variáveis, o alerta é salvo em saidas/alertas/alerta_AAAA-MM-DD.html para conferência.

Como rodar:
    python modelo/alerta_churn.py

Como agendar (Agendador de Tarefas do Windows, toda segunda às 8h):
    schtasks /create /tn "AlertaChurn" /sc weekly /d MON /st 08:00 /tr "python \"C:\\caminho\\do\\projeto\\modelo\\alerta_churn.py\""
"""

import os
import smtplib
from email.mime.text import MIMEText

import pandas as pd

from modelo_churn import PASTA_SAIDAS, executar

PASTA_ALERTAS = PASTA_SAIDAS / "alertas"
CAMINHO_ESTADO = PASTA_ALERTAS / "estado_anterior.csv"
JANELA_DIAS = 30        # cancelamentos dos últimos 30 dias entram no alerta


def carregar_estado_anterior():
    """Lê o estado salvo na última execução. Se não existir (primeira execução), retorna uma tabela vazia."""

    if CAMINHO_ESTADO.exists():
        return pd.read_csv(CAMINHO_ESTADO)

    return pd.DataFrame(columns=["id_contrato", "status", "nivel_risco"])


def montar_listas(contratos, scores, estado_anterior, hoje):
    """Compara a situação atual com a anterior e devolve as três listas do alerta."""

    # 1. contratos cancelados recentemente
    inicio_janela = hoje - pd.Timedelta(days=JANELA_DIAS)
    entraram_churn = contratos[contratos["data_cancelamento"] >= inicio_janela]
    entraram_churn = entraram_churn[
        ["id_contrato", "cpf", "uf", "nome_plano", "mrr_mensal", "data_inicio", "data_cancelamento"]
    ].sort_values("data_cancelamento", ascending=False)

    # 2. contratos em risco alto que não estavam em risco alto antes
    alto_antes = estado_anterior.loc[estado_anterior["nivel_risco"] == "Alto", "id_contrato"]
    entraram_risco_alto = scores[(scores["nivel_risco"] == "Alto") & (~scores["id_contrato"].isin(alto_antes))]

    # 3. contratos que viraram inadimplentes
    inadimplentes_antes = estado_anterior.loc[estado_anterior["status"] == "Inadimplente", "id_contrato"]
    novos_inadimplentes = scores[(scores["status"] == "Inadimplente") & (~scores["id_contrato"].isin(inadimplentes_antes))]

    colunas_risco = [
        "id_contrato", "cpf", "uf", "nome_plano", "mrr_mensal", "meses_de_casa", "probabilidade_churn", "motivo_risco",
    ]

    return entraram_churn, entraram_risco_alto[colunas_risco], novos_inadimplentes[colunas_risco]


def montar_email(entraram_churn, entraram_risco_alto, novos_inadimplentes, scores, hoje):
    """Monta o corpo do e-mail em html usando o to_html do pandas."""

    def secao(titulo, descricao, tabela):
        if tabela.empty:
            return f"<h3>{titulo}</h3><p>Nenhum contrato nesta situação.</p>"
        mrr = tabela["mrr_mensal"].sum()
        return (
            f"<h3>{titulo} ({len(tabela)} contratos | MRR R$ {mrr:,.2f})</h3>"
            f"<p>{descricao}</p>"
            + tabela.to_html(index=False, float_format=lambda x: f"{x:,.2f}", border=0)
        )

    resumo = scores.groupby("nivel_risco").agg(contratos=("id_contrato", "size"), mrr=("mrr_mensal", "sum"))

    return (
        f"<h2>Alerta de churn - {hoje:%d/%m/%Y}</h2>"
        + "<h3>Carteira ativa por nível de risco</h3>"
        + resumo.to_html(float_format=lambda x: f"{x:,.2f}", border=0)
        + secao("Entraram em churn", f"Contratos cancelados nos últimos {JANELA_DIAS} dias.", entraram_churn)
        + secao(
            "Entraram em risco alto",
            "Contratos com maior chance de cancelar nos próximos 6 meses. Prioridade de contato do CS.",
            entraram_risco_alto,
        )
        + secao("Novos inadimplentes", "Contratos que passaram a ficar inadimplentes desde o último alerta.", novos_inadimplentes)
    )


def enviar_email(html, hoje):
    """Envia o e-mail se o SMTP estiver configurado. Caso contrário, salva o html para conferência."""

    destinatarios = os.getenv("ALERTA_DESTINATARIOS")
    servidor = os.getenv("SMTP_SERVIDOR")

    if not destinatarios or not servidor:
        caminho = PASTA_ALERTAS / f"alerta_{hoje:%Y-%m-%d}.html"
        caminho.write_text(html, encoding="utf-8")
        print(f"SMTP não configurado. Alerta salvo em {caminho}")
        return

    mensagem = MIMEText(html, "html", "utf-8")
    mensagem["Subject"] = f"Alerta de churn - {hoje:%d/%m/%Y}"
    mensagem["From"] = os.getenv("SMTP_USUARIO")
    mensagem["To"] = destinatarios

    with smtplib.SMTP(servidor, int(os.getenv("SMTP_PORTA", "587"))) as smtp:
        smtp.starttls()
        smtp.login(os.getenv("SMTP_USUARIO"), os.getenv("SMTP_SENHA"))
        smtp.send_message(mensagem)

    print(f"Alerta enviado para {destinatarios}")


def main():
    PASTA_ALERTAS.mkdir(parents=True, exist_ok=True)
    hoje = pd.Timestamp.today().normalize()

    contratos, scores = executar()
    estado_anterior = carregar_estado_anterior()

    entraram_churn, entraram_risco_alto, novos_inadimplentes = montar_listas(contratos, scores, estado_anterior, hoje)

    print(f"Entraram em churn: {len(entraram_churn)}")
    print(f"Entraram em risco alto: {len(entraram_risco_alto)}")
    print(f"Novos inadimplentes: {len(novos_inadimplentes)}")

    html = montar_email(entraram_churn, entraram_risco_alto, novos_inadimplentes, scores, hoje)
    enviar_email(html, hoje)

    # salvando o estado atual só depois do envio, para não perder alertas se algo falhar no meio
    scores[["id_contrato", "status", "nivel_risco"]].to_csv(CAMINHO_ESTADO, index=False)


if __name__ == "__main__":
    main()
