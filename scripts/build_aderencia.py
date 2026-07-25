#!/usr/bin/env python3
"""
build_aderencia.py
-------------------
Lê a base Producao_Semanal_PowerBI.xlsx (aderência semanal de produção) e
gera o dashboard estático docs/aderencia/index.html, replicando o relatório
Power BI "KPI Aderência".

Uso:
    python scripts/build_aderencia.py

Fórmulas (validadas linha a linha contra o PDF original):
    Demandado x Produzido  = SUM(Produzido Ajustado KG) / SUM(Demanda KG)
    Demandado x Programado = SUM(Programado Ajustado KG) / SUM(Demanda KG)
    Programado x Produzido = SUM(Produzido Ajustado KG) / SUM(Programado Ajustado KG)
    Aderência Bruta (por produto) = SUM(Produzido KG) / SUM(Programado KG)
    "Dentro da Meta" = Aderência Bruta entre 95% e 105% (inclusive)
"""
import json
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "aderencia" / "Producao_Semanal_PowerBI.xlsx"
TEMA_PATH = BASE_DIR / "data" / "aderencia" / "Tema.json"
OUTPUT_PATH = BASE_DIR / "docs" / "aderencia" / "index.html"
TEMPLATE_PATH = BASE_DIR / "scripts" / "template_aderencia.html"

MES_ORDEM = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
             "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def carregar_dados() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH, sheet_name="Dados_Consolidados", header=0)
    df = df.copy()
    df["Data Início Semana"] = pd.to_datetime(df["Data Início Semana"], errors="coerce")
    for c in ["Programado (KG)", "Programado Ajustado (KG)", "Produzido (KG)",
              "Produzido Ajustado (KG)", "Demanda (KG)", "Produzido (UN)"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # Às vezes a planilha vem com Ano / Mês / Mês Nº vazios (colunas calculadas
    # no Power BI que não são gravadas como valor no .xlsx). Nesses casos,
    # recalcula a partir de "Data Início Semana", que sempre vem preenchida.
    precisa_recalcular = (
        df["Ano"].isna().any() or df["Mês"].isna().any() or df["Mês Nº"].isna().any()
    )
    if precisa_recalcular:
        df["Ano"] = df["Ano"].astype(object)
        df["Mês"] = df["Mês"].astype(object)
        df["Mês Nº"] = df["Mês Nº"].astype(object)
        com_data = df["Data Início Semana"].notna()
        df.loc[com_data, "Ano"] = df.loc[com_data, "Data Início Semana"].dt.year
        mes_num_calc = df.loc[com_data, "Data Início Semana"].dt.month
        df.loc[com_data, "Mês Nº"] = mes_num_calc
        df.loc[com_data, "Mês"] = mes_num_calc.map(lambda n: MES_ORDEM[int(n) - 1])
        faltando = df["Ano"].isna().sum()
        if faltando:
            print(f"[aviso] {faltando} linha(s) sem 'Data Início Semana' e sem Ano/Mês "
                  f"preenchidos — serão descartadas.")
            df = df[df["Ano"].notna()]

    return df


def montar_registros(df: pd.DataFrame) -> list:
    registros = []
    for _, row in df.iterrows():
        registros.append({
            "ano": int(row["Ano"]),
            "mes": row["Mês"],
            "mes_num": int(row["Mês Nº"]),
            "semana": row["Semana"],
            "num_semana": int(row["Nº Semana"]),
            "data_inicio": (
                row["Data Início Semana"].strftime("%d/%m/%Y")
                if pd.notna(row["Data Início Semana"]) else None
            ),
            "produto": row["Produto"],
            "setor": row["Setor"],
            "programado_kg": round(float(row["Programado (KG)"]), 2),
            "programado_ajustado_kg": round(float(row["Programado Ajustado (KG)"]), 2),
            "produzido_kg": round(float(row["Produzido (KG)"]), 2),
            "produzido_ajustado_kg": round(float(row["Produzido Ajustado (KG)"]), 2),
            "produzido_un": round(float(row["Produzido (UN)"]), 1),
            "demanda_kg": round(float(row["Demanda (KG)"]), 2),
            "comentario": row["Comentários"] if pd.notna(row["Comentários"]) else None,
        })
    return registros


def montar_filtros(df: pd.DataFrame) -> dict:
    meses = (
        df[["Ano", "Mês", "Mês Nº"]]
        .drop_duplicates()
        .sort_values(["Ano", "Mês Nº"])
    )
    meses_lista = [
        {"ano": int(r["Ano"]), "mes": r["Mês"], "mes_num": int(r["Mês Nº"]),
         "label": f'{r["Mês"]}/{r["Ano"]}'}
        for _, r in meses.iterrows()
    ]

    setores = sorted(df["Setor"].unique())
    produtos = (
        df[["Produto", "Setor"]].drop_duplicates().sort_values("Produto")
    )
    produtos_lista = [
        {"nome": r["Produto"], "setor": r["Setor"]} for _, r in produtos.iterrows()
    ]

    return {"meses": meses_lista, "setores": setores, "produtos": produtos_lista}


def gerar_html(payload: dict, tema: dict | None) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__ADERENCIA_DATA__", json.dumps(payload, ensure_ascii=False))
    html = html.replace("__THEME_DATA__", json.dumps(tema or {}, ensure_ascii=False))
    return html


def main():
    if not DATA_PATH.exists():
        raise SystemExit(f"Não encontrei {DATA_PATH}.")

    df = carregar_dados()

    tema = None
    if TEMA_PATH.exists():
        tema = json.loads(TEMA_PATH.read_text(encoding="utf-8-sig"))

    payload = {
        "gerado_em": pd.Timestamp.now().strftime("%d/%m/%Y %H:%M"),
        "filtros": montar_filtros(df),
        "registros": montar_registros(df),
    }

    html = gerar_html(payload, tema)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")

    print(f"Dashboard gerado em: {OUTPUT_PATH}")
    print(f"Registros: {len(payload['registros'])} | Meses: {[m['label'] for m in payload['filtros']['meses']]}")


if __name__ == "__main__":
    main()
