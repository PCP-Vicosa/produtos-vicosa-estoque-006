#!/usr/bin/env python3
"""
build_dashboard.py
-------------------
Lê a base BD_006.xlsx (histórico diário de estoque do Depósito 006) e gera
um dashboard estático em HTML (docs/index.html), pronto para publicar no
GitHub Pages.

Uso:
    python scripts/build_dashboard.py

Espera encontrar o arquivo em: data/BD_006.xlsx
Gera o arquivo em:            docs/index.html

Colunas usadas da planilha (nomes reais do BD_006.xlsx):
    Data Estoque, Família, Lote Fab., Produto, Saldo Lote,
    Data Validade, Data Fab. Lote, Descrição Produto
"""
import json
import re
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "BD_006.xlsx"
OUTPUT_PATH = BASE_DIR / "docs" / "index.html"
TEMPLATE_PATH = BASE_DIR / "scripts" / "template.html"


def nome_produto(descricao: str) -> str:
    """A coluna 'Descrição Produto' vem no formato
    'NOME CURTO - nome longo - derivação - derivação'.
    Usamos só a primeira parte, que é o nome comercial do produto."""
    if not isinstance(descricao, str):
        return "Produto sem nome"
    return descricao.split(" - ")[0].strip()


def carregar_dados(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, header=0)

    colunas_esperadas = [
        "Data Estoque", "Família", "Lote Fab.", "Produto", "Saldo Lote",
        "Data Validade", "Data Fab. Lote", "Descrição Produto",
    ]
    faltando = [c for c in colunas_esperadas if c not in df.columns]
    if faltando:
        raise ValueError(
            f"As colunas a seguir não foram encontradas no BD_006.xlsx: {faltando}. "
            f"Colunas disponíveis: {list(df.columns)}"
        )

    df = df.copy()
    df["Data Estoque"] = pd.to_datetime(df["Data Estoque"]).dt.normalize()
    df["Data Validade"] = pd.to_datetime(df["Data Validade"], errors="coerce")
    df["Data Fab. Lote"] = pd.to_datetime(df["Data Fab. Lote"], errors="coerce")
    df["Saldo Lote"] = pd.to_numeric(df["Saldo Lote"], errors="coerce").fillna(0)
    df["Produto Nome"] = df["Descrição Produto"].apply(nome_produto)
    df["Família"] = df["Família"].astype(str).str.zfill(3)

    return df


def montar_series_diarias(df: pd.DataFrame) -> dict:
    """Saldo total por Produto x Dia (para o gráfico de evolução)."""
    agrupado = (
        df.groupby(["Produto Nome", "Data Estoque"])["Saldo Lote"]
        .sum()
        .reset_index()
    )

    datas = sorted(agrupado["Data Estoque"].unique())
    datas_str = [pd.Timestamp(d).strftime("%d/%m/%Y") for d in datas]

    series = {}
    for produto, grupo in agrupado.groupby("Produto Nome"):
        mapa = dict(zip(grupo["Data Estoque"], grupo["Saldo Lote"]))
        valores = [round(float(mapa.get(d, 0)), 2) for d in datas]
        series[produto] = valores

    return {"datas": datas_str, "series": series}


def montar_lotes_atuais(df: pd.DataFrame) -> dict:
    """Para cada produto, a foto do último dia disponível: lote a lote,
    com saldo, data de fabricação e validade."""
    ultima_data = df["Data Estoque"].max()
    hoje = df_ultimo = df[df["Data Estoque"] == ultima_data].copy()

    df_ultimo = df_ultimo[df_ultimo["Saldo Lote"] > 0]

    lotes_por_produto = {}
    for produto, grupo in df_ultimo.groupby("Produto Nome"):
        linhas = []
        for _, row in grupo.sort_values("Data Validade").iterrows():
            linhas.append({
                "lote": str(row["Lote Fab."]),
                "saldo": round(float(row["Saldo Lote"]), 2),
                "fabricacao": (
                    row["Data Fab. Lote"].strftime("%d/%m/%Y")
                    if pd.notna(row["Data Fab. Lote"]) else "-"
                ),
                "validade": (
                    row["Data Validade"].strftime("%d/%m/%Y")
                    if pd.notna(row["Data Validade"]) else "-"
                ),
                "dias_para_vencer": (
                    (row["Data Validade"] - ultima_data).days
                    if pd.notna(row["Data Validade"]) else None
                ),
            })
        lotes_por_produto[produto] = linhas

    return {
        "ultima_data": ultima_data.strftime("%d/%m/%Y"),
        "lotes": lotes_por_produto,
    }


def montar_resumo_produtos(df: pd.DataFrame) -> list:
    """Lista de produtos com saldo atual e variação frente ao dia anterior,
    para popular o filtro e os cartões de resumo."""
    datas = sorted(df["Data Estoque"].unique())
    ultima_data = datas[-1]
    penultima_data = datas[-2] if len(datas) > 1 else None

    saldo_atual = (
        df[df["Data Estoque"] == ultima_data]
        .groupby("Produto Nome")["Saldo Lote"].sum()
    )
    saldo_anterior = (
        df[df["Data Estoque"] == penultima_data]
        .groupby("Produto Nome")["Saldo Lote"].sum()
        if penultima_data is not None else pd.Series(dtype=float)
    )

    familia_por_produto = (
        df.sort_values("Data Estoque")
        .groupby("Produto Nome")["Família"].last()
    )

    resumo = []
    for produto in sorted(saldo_atual.index):
        atual = float(saldo_atual.get(produto, 0))
        anterior = float(saldo_anterior.get(produto, 0))
        resumo.append({
            "produto": produto,
            "familia": familia_por_produto.get(produto, "-"),
            "saldo_atual": round(atual, 2),
            "saldo_anterior": round(anterior, 2),
            "variacao": round(atual - anterior, 2),
        })

    return resumo


def gerar_html(payload: dict) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    dados_json = json.dumps(payload, ensure_ascii=False)
    return template.replace("__DASHBOARD_DATA__", dados_json)


def main():
    if not DATA_PATH.exists():
        raise SystemExit(
            f"Não encontrei {DATA_PATH}. Copie o BD_006.xlsx para a pasta data/ "
            f"antes de rodar este script."
        )

    df = carregar_dados(DATA_PATH)

    payload = {
        "gerado_em": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
        "evolucao": montar_series_diarias(df),
        "lotes": montar_lotes_atuais(df),
        "resumo": montar_resumo_produtos(df),
    }

    html = gerar_html(payload)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard gerado em: {OUTPUT_PATH}")
    print(f"Produtos: {len(payload['resumo'])} | Dias: {len(payload['evolucao']['datas'])}")


if __name__ == "__main__":
    main()
