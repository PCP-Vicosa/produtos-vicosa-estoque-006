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


def _mes_num_semana(data_inicio: pd.Timestamp) -> int:
    """Replica a fórmula da planilha para decidir a que mês uma semana
    "pertence" quando ela cruza a virada do mês:
    =IF(MONTH(E+1)=MONTH(E+6), MONTH(E+1),
        IF(MIN(EOMONTH(E+1,0),E+6)-(E+1)+1>=3, MONTH(E+1), MONTH(E+6)))
    """
    d1 = data_inicio + pd.Timedelta(days=1)
    d6 = data_inicio + pd.Timedelta(days=6)
    if d1.month == d6.month:
        return d1.month
    fim_mes_d1 = d1 + pd.offsets.MonthEnd(0)
    limite = min(fim_mes_d1, d6)
    dias_no_mes_d1 = (limite - d1).days + 1
    return d1.month if dias_no_mes_d1 >= 3 else d6.month


def carregar_dados() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH, sheet_name="Dados_Consolidados", header=0)
    df = df.copy()
    df["Data Início Semana"] = pd.to_datetime(df["Data Início Semana"], errors="coerce")
    for c in ["Gramatura (KG)", "Programado (UN)", "Produzido (UN)", "Demanda (UN)",
              "Programado (KG)", "Programado Ajustado (KG)", "Produzido (KG)",
              "Produzido Ajustado (KG)", "Demanda (KG)"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    com_data = df["Data Início Semana"].notna()

    # Às vezes a planilha vem com colunas calculadas do Excel/Power BI vazias
    # (fórmula presente na célula, mas sem valor em cache — acontece quando o
    # arquivo é salvo/gerado sem recalcular). Nesses casos, recalcula a partir
    # das colunas "cruas" (UN, Gramatura, Data Início Semana), replicando as
    # mesmas fórmulas da planilha original.
    if df["Ano"].isna().any() or df["Mês"].isna().any() or df["Mês Nº"].isna().any():
        df["Ano"] = df["Ano"].astype(object)
        df["Mês"] = df["Mês"].astype(object)
        df["Mês Nº"] = df["Mês Nº"].astype(object)
        df.loc[com_data, "Ano"] = df.loc[com_data, "Data Início Semana"].dt.year
        mes_num_calc = df.loc[com_data, "Data Início Semana"].apply(_mes_num_semana)
        df.loc[com_data, "Mês Nº"] = mes_num_calc
        df.loc[com_data, "Mês"] = mes_num_calc.map(lambda n: MES_ORDEM[int(n) - 1])

    faltando = df["Ano"].isna().sum()
    if faltando:
        print(f"[aviso] {faltando} linha(s) sem 'Data Início Semana' e sem Ano/Mês "
              f"preenchidos — serão descartadas.")
        df = df[df["Ano"].notna()]

    gram = df["Gramatura (KG)"].fillna(0)
    prog_un = df["Programado (UN)"].fillna(0)
    prod_un = df["Produzido (UN)"].fillna(0)
    dem_un = df["Demanda (UN)"].fillna(0)

    if df["Programado (KG)"].isna().any():
        df["Programado (KG)"] = prog_un * gram
    if df["Produzido (KG)"].isna().any():
        df["Produzido (KG)"] = prod_un * gram
    if df["Demanda (KG)"].isna().any():
        df["Demanda (KG)"] = dem_un * gram

    if df["Programado Ajustado (KG)"].isna().any():
        prog_kg = df["Programado (KG)"]
        dem_kg = df["Demanda (KG)"]
        df["Programado Ajustado (KG)"] = [
            0 if d == 0 else (d if p / d > 1 else p) for p, d in zip(prog_kg, dem_kg)
        ]

    if df["Produzido Ajustado (KG)"].isna().any():
        prod_kg = df["Produzido (KG)"]
        prog_ajust = df["Programado Ajustado (KG)"]
        df["Produzido Ajustado (KG)"] = [
            0 if pa == 0 else (pa if pr / pa > 1 else pr)
            for pr, pa in zip(prod_kg, prog_ajust)
        ]

    for c in ["Programado (KG)", "Programado Ajustado (KG)", "Produzido (KG)",
              "Produzido Ajustado (KG)", "Demanda (KG)", "Produzido (UN)"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

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
        "gerado_em": pd.Timestamp.now(tz="America/Sao_Paulo").strftime("%d/%m/%Y %H:%M"),
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
