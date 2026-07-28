#!/usr/bin/env python3
"""
build_dashboard.py
-------------------
Lê a base BD_006.xlsx (histórico diário de estoque do Depósito 006), junto com
as tabelas de apoio (peso por produto e nome curto), e gera um dashboard
estático em HTML (docs/index.html) que replica as 3 páginas do relatório
Power BI original, pronto para publicar no GitHub Pages.

Uso:
    python scripts/build_dashboard.py

Arquivos de entrada (pasta data/):
    BD_006.xlsx                  - base de estoque diário
    Dim_Peso_Produto.csv         - peso (kg) por unidade de cada produto
    Dim_Nome_Curto_Produto.csv   - nome comercial curto de cada produto
    Tema.json                    - tema de cores exportado do Power BI (opcional)

Saída:
    docs/index.html
"""
import json
import re
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BD_PATH = DATA_DIR / "BD_006.xlsx"
PESO_PATH = DATA_DIR / "Dim_Peso_Produto.csv"
NOME_PATH = DATA_DIR / "Dim_Nome_Curto_Produto.csv"
OUTPUT_PATH = BASE_DIR / "docs" / "estoque-006" / "index.html"
TEMPLATE_PATH = BASE_DIR / "scripts" / "template.html"

# Código da Família (coluna "Família" do BD_006) -> nome do Setor.
# Levantado comparando os produtos de cada família com os setores do
# relatório Power BI original (Doce, Iogurte, Manteiga, Queijo, Leite,
# Requeijão).
SETOR_POR_FAMILIA = {
    "003": "Iogurte",
    "005": "Doce",
    "006": "Manteiga",
    "007": "Queijo",
    "008": "Leite",
    "009": "Requeijão",
}


def carregar_dimensoes():
    peso = pd.read_csv(PESO_PATH, sep=";", decimal=",", dtype={"Produto": str})
    peso["Produto"] = peso["Produto"].str.zfill(10)
    peso = peso.set_index("Produto")["Gramatura_KG"]

    nomes = pd.read_csv(NOME_PATH, sep=";", dtype={"Produto": str})
    nomes["Produto"] = nomes["Produto"].str.zfill(10)
    nomes = nomes.set_index("Produto")["Nome_Curto"]

    return peso, nomes


def carregar_dados() -> pd.DataFrame:
    df = pd.read_excel(BD_PATH, sheet_name=0, header=0)

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
    df["Família"] = df["Família"].astype(str).str.zfill(3)
    df["Produto Cod"] = df["Produto"].astype(str).str.zfill(10)
    df["Setor"] = df["Família"].map(SETOR_POR_FAMILIA).fillna("Outros")

    peso, nomes = carregar_dimensoes()
    df["Gramatura_KG"] = df["Produto Cod"].map(peso)
    faltando_peso = df.loc[df["Gramatura_KG"].isna(), "Produto Cod"].unique()
    if len(faltando_peso) > 0:
        print(f"[aviso] {len(faltando_peso)} produto(s) sem peso cadastrado em "
              f"Dim_Peso_Produto.csv (tratados como 0 kg): {list(faltando_peso)[:10]}")
        df["Gramatura_KG"] = df["Gramatura_KG"].fillna(0)

    df["Nome Curto"] = df["Produto Cod"].map(nomes)
    df["Nome Curto"] = df["Nome Curto"].fillna(
        df["Descrição Produto"].apply(nome_produto_fallback)
    )

    df["Saldo KG"] = df["Saldo Lote"] * df["Gramatura_KG"]

    return df


def nome_produto_fallback(descricao) -> str:
    if not isinstance(descricao, str):
        return "Produto sem nome"
    return descricao.split(" - ")[0].strip()


def fmt_data(d):
    return pd.Timestamp(d).strftime("%d/%m/%Y") if pd.notna(d) else None


def montar_filtros(df: pd.DataFrame) -> dict:
    setores = sorted(df["Setor"].unique())
    produtos = (
        df[["Produto Cod", "Nome Curto", "Setor"]]
        .drop_duplicates()
        .sort_values("Nome Curto")
    )
    produtos_lista = [
        {"codigo": r["Produto Cod"], "nome": r["Nome Curto"], "setor": r["Setor"]}
        for _, r in produtos.iterrows()
    ]
    datas = sorted(df["Data Estoque"].unique())
    return {
        "setores": setores,
        "produtos": produtos_lista,
        "datas": [fmt_data(d) for d in datas],
    }


def montar_evolucao_geral(df: pd.DataFrame) -> dict:
    """Saldo total (kg) por dia, geral e por setor — usado nos cards e no
    gráfico de linha da página 'Visão Geral'."""
    datas = sorted(df["Data Estoque"].unique())
    total_por_dia = df.groupby("Data Estoque")["Saldo KG"].sum()
    setor_por_dia = df.groupby(["Setor", "Data Estoque"])["Saldo KG"].sum()
    # Mesma serie em unidades, para o botao kg/Unidade do grafico "Saldo por
    # Setor". Um setor pesado domina em kg e encolhe em unidade — sao duas
    # leituras diferentes do mesmo saldo.
    setor_por_dia_un = df.groupby(["Setor", "Data Estoque"])["Saldo Lote"].sum()

    setores = sorted(df["Setor"].unique())
    return {
        "datas": [fmt_data(d) for d in datas],
        "total_kg": [round(float(total_por_dia.get(d, 0)), 1) for d in datas],
        "por_setor": {
            setor: [round(float(setor_por_dia.get((setor, d), 0)), 1) for d in datas]
            for setor in setores
        },
        "por_setor_un": {
            setor: [int(setor_por_dia_un.get((setor, d), 0)) for d in datas]
            for setor in setores
        },
    }


def montar_evolucao_sku(df: pd.DataFrame) -> dict:
    """Saldo (kg) por dia, por Setor e por SKU (Nome Curto) — usado na
    página 'Família / SKU' (gráfico de linha por setor + waterfall)."""
    datas = sorted(df["Data Estoque"].unique())
    datas_fmt = [fmt_data(d) for d in datas]

    chave = ["Setor", "Nome Curto", "Data Estoque"]
    agrup = df.groupby(chave)["Saldo KG"].sum()
    # Mesma serie em unidades (caixas/pecas), para o botao kg/unidade da
    # interface. Sao duas leituras diferentes do mesmo saldo: um SKU pesado
    # domina em kg e some em unidade, e vice-versa.
    agrup_un = df.groupby(chave)["Saldo Lote"].sum()

    resultado, resultado_un = {}, {}
    for setor, grupo in df.groupby("Setor"):
        skus = sorted(grupo["Nome Curto"].unique())
        resultado[setor] = {
            sku: [round(float(agrup.get((setor, sku, d), 0)), 1) for d in datas]
            for sku in skus
        }
        resultado_un[setor] = {
            sku: [int(agrup_un.get((setor, sku, d), 0)) for d in datas]
            for sku in skus
        }

    return {"datas": datas_fmt, "por_setor_sku": resultado,
            "por_setor_sku_un": resultado_un}


def montar_lotes_por_data(df: pd.DataFrame) -> dict:
    """Para cada data disponível, a lista de lotes com saldo > 0, com todos
    os campos usados nas tabelas da página 'Lotes' (fabricação, validade,
    saldo un/kg, dias para vencer, % de validade restante)."""
    resultado = {}
    for data, grupo in df.groupby("Data Estoque"):
        grupo = grupo[grupo["Saldo Lote"] > 0]
        linhas = []
        for _, row in grupo.iterrows():
            # dias/pct calculados com base na data da leitura (snapshot) —
            # mantidos apenas como referência histórica; o dashboard recalcula
            # esses valores no navegador em relação à data real de hoje.
            dias_para_vencer_snapshot = (
                (row["Data Validade"] - data).days
                if pd.notna(row["Data Validade"]) else None
            )
            vida_total = (
                (row["Data Validade"] - row["Data Fab. Lote"]).days
                if pd.notna(row["Data Validade"]) and pd.notna(row["Data Fab. Lote"])
                else None
            )
            pct_validade_snapshot = (
                round(100 * dias_para_vencer_snapshot / vida_total, 2)
                if vida_total and vida_total > 0 and dias_para_vencer_snapshot is not None
                else None
            )
            linhas.append({
                "setor": row["Setor"],
                "produto": row["Produto Cod"],
                "nome": row["Nome Curto"],
                "lote": str(row["Lote Fab."]),
                "fabricacao": fmt_data(row["Data Fab. Lote"]),
                "fabricacao_iso": (
                    row["Data Fab. Lote"].strftime("%Y-%m-%d")
                    if pd.notna(row["Data Fab. Lote"]) else None
                ),
                "validade": fmt_data(row["Data Validade"]),
                "validade_iso": (
                    row["Data Validade"].strftime("%Y-%m-%d")
                    if pd.notna(row["Data Validade"]) else None
                ),
                "vida_total_dias": vida_total,
                "saldo_un": round(float(row["Saldo Lote"]), 2),
                "saldo_kg": round(float(row["Saldo KG"]), 2),
                "dias_para_vencer_snapshot": dias_para_vencer_snapshot,
                "pct_validade_snapshot": pct_validade_snapshot,
            })
        resultado[fmt_data(data)] = linhas
    return resultado


def montar_cobertura(df: pd.DataFrame) -> dict:
    """Consumo diario e cobertura em dias, por SKU.

    METODOLOGIA (fixada aqui de proposito — o resultado muda bastante
    conforme a escolha, entao ela precisa estar escrita no codigo):

      consumo total do SKU = soma de todas as REDUCOES de saldo, lote a lote,
                             entre snapshots consecutivos, ao longo de todo o
                             periodo disponivel. Aumentos (producao nova
                             entrando) nao entram na conta.
      consumo diario       = consumo total / dias corridos entre o primeiro e
                             o ultimo snapshot.
      cobertura em dias    = saldo atual / consumo diario.

    Um SKU sem nenhuma reducao observada fica sem cobertura (None), e nao
    com cobertura infinita — sao coisas diferentes e a interface precisa
    distinguir.
    """
    datas = sorted(df["Data Estoque"].dropna().unique())
    if len(datas) < 2:
        return {"dias_serie": 0, "por_sku": {}, "mediana": None}

    dias_serie = (pd.Timestamp(datas[-1]) - pd.Timestamp(datas[0])).days or 1

    # saldo em kg por (data, sku, lote)
    chave = ["Data Estoque", "Produto Cod", "Lote Fab."]
    saldo = df.groupby(chave)["Saldo KG"].sum()

    consumo = {}
    for i in range(1, len(datas)):
        ant = saldo.loc[datas[i - 1]] if datas[i - 1] in saldo.index.get_level_values(0) else None
        atu = saldo.loc[datas[i]] if datas[i] in saldo.index.get_level_values(0) else None
        if ant is None or atu is None:
            continue
        delta = ant.subtract(atu, fill_value=0.0)   # positivo = saiu
        delta = delta[delta > 0]
        for (sku, _lote), v in delta.items():
            consumo[sku] = consumo.get(sku, 0.0) + float(v)

    ultima = datas[-1]
    atual = (df[df["Data Estoque"] == ultima]
             .groupby("Produto Cod")
             .agg(kg=("Saldo KG", "sum"), nome=("Nome Curto", "first"),
                  setor=("Setor", "first")))

    por_sku, coberturas = {}, []
    for sku, row in atual.iterrows():
        total = consumo.get(sku, 0.0)
        diario = total / dias_serie if total > 0 else 0.0
        cob = round(float(row["kg"]) / diario, 1) if diario > 0 else None
        por_sku[sku] = {
            "nome": row["nome"], "setor": row["setor"],
            "saldo_kg": round(float(row["kg"]), 2),
            "consumo_dia_kg": round(diario, 2),
            "cobertura_dias": cob,
        }
        if cob is not None:
            coberturas.append(cob)

    coberturas.sort()
    mediana = None
    if coberturas:
        m = len(coberturas) // 2
        mediana = (coberturas[m] if len(coberturas) % 2
                   else round((coberturas[m - 1] + coberturas[m]) / 2, 1))

    return {
        "dias_serie": dias_serie,
        "mediana": mediana,
        "sem_consumo": int(sum(1 for v in por_sku.values() if v["cobertura_dias"] is None)),
        "criticos": int(sum(1 for c in coberturas if c < 2)),
        "excesso": int(sum(1 for c in coberturas if c > 30)),
        "por_sku": por_sku,
    }


FAIXAS = [
    ("0-25%", 0, 25), ("25-50%", 25, 50), ("50-75%", 50, 75),
    ("75-100%", 75, 100),
]


def montar_faixas_validade(df: pd.DataFrame) -> dict:
    """Distribuicao dos lotes por percentual de VIDA UTIL JA CONSUMIDA.

    A convencao e sempre 'consumida', nunca 'restante' — a inversao das duas
    leituras era uma fonte de confusao na interface. 0-25% = lote novo.
    """
    ultima = df["Data Estoque"].max()
    g = df[(df["Data Estoque"] == ultima) & (df["Saldo Lote"] > 0)].copy()

    vida = (g["Data Validade"] - g["Data Fab. Lote"]).dt.days
    idade = (ultima - g["Data Fab. Lote"]).dt.days
    g["pct_consumido"] = (100 * idade / vida).where(vida > 0)
    g["vencido"] = g["Data Validade"] < ultima

    faixas = []
    for rotulo, ini, fim in FAIXAS:
        m = (~g["vencido"]) & (g["pct_consumido"] >= ini) & (g["pct_consumido"] < fim)
        faixas.append({"faixa": rotulo, "lotes": int(m.sum()),
                       "kg": round(float(g.loc[m, "Saldo KG"].sum()), 2),
                       "un": int(g.loc[m, "Saldo Lote"].sum())})
    m = g["vencido"]
    faixas.append({"faixa": "Vencido", "lotes": int(m.sum()),
                   "kg": round(float(g.loc[m, "Saldo KG"].sum()), 2),
                   "un": int(g.loc[m, "Saldo Lote"].sum())})

    dias_venc = (g["Data Validade"] - ultima).dt.days
    return {
        "data": fmt_data(ultima),
        "faixas": faixas,
        "kg_7dias": round(float(g.loc[(dias_venc >= 0) & (dias_venc <= 7), "Saldo KG"].sum()), 2),
        "kg_30dias": round(float(g.loc[(dias_venc >= 0) & (dias_venc <= 30), "Saldo KG"].sum()), 2),
    }


def montar_reservado(df: pd.DataFrame) -> dict:
    """Separa o que esta em estoque do que ja esta comprometido."""
    ultima = df["Data Estoque"].max()
    g = df[df["Data Estoque"] == ultima]
    if "Qtd. Reservada" not in g.columns:
        return {"disponivel": False}
    res_un = pd.to_numeric(g["Qtd. Reservada"], errors="coerce").fillna(0)
    gram = g["Saldo KG"] / g["Saldo Lote"].replace(0, pd.NA)
    res_kg = float((res_un * gram.fillna(0)).sum())
    total_kg = float(g["Saldo KG"].sum())
    return {
        "disponivel": True,
        "reservado_kg": round(res_kg, 2),
        "livre_kg": round(total_kg - res_kg, 2),
        "lotes_com_reserva": int((res_un > 0).sum()),
    }


def gerar_html(payload: dict, tema: dict | None) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    dados_json = json.dumps(payload, ensure_ascii=False)
    html = template.replace("__DASHBOARD_DATA__", dados_json)
    tema_json = json.dumps(tema or {}, ensure_ascii=False)
    html = html.replace("__THEME_DATA__", tema_json)
    return html


def main():
    if not BD_PATH.exists():
        raise SystemExit(f"Não encontrei {BD_PATH}. Copie o BD_006.xlsx para a pasta data/.")
    if not PESO_PATH.exists() or not NOME_PATH.exists():
        raise SystemExit(
            "Faltam Dim_Peso_Produto.csv e/ou Dim_Nome_Curto_Produto.csv na pasta data/."
        )

    df = carregar_dados()

    tema = None
    tema_path = DATA_DIR / "Tema.json"
    if tema_path.exists():
        tema = json.loads(tema_path.read_text(encoding="utf-8-sig"))

    payload = {
        "gerado_em": pd.Timestamp.now(tz="America/Sao_Paulo").strftime("%d/%m/%Y %H:%M"),
        "filtros": montar_filtros(df),
        "evolucao_geral": montar_evolucao_geral(df),
        "evolucao_sku": montar_evolucao_sku(df),
        "lotes_por_data": montar_lotes_por_data(df),
        "cobertura": montar_cobertura(df),
        "faixas_validade": montar_faixas_validade(df),
        "reservado": montar_reservado(df),
    }

    html = gerar_html(payload, tema)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")

    ultima_data = payload["filtros"]["datas"][-1]
    total_kg_ultima = payload["evolucao_geral"]["total_kg"][-1]
    print(f"Dashboard gerado em: {OUTPUT_PATH}")
    print(f"Dias: {len(payload['filtros']['datas'])} | Setores: {payload['filtros']['setores']}")
    print(f"Saldo total em {ultima_data}: {total_kg_ultima:,.1f} kg")
    for setor in payload["filtros"]["setores"]:
        v = payload["evolucao_geral"]["por_setor"][setor][-1]
        print(f"  {setor}: {v:,.1f} kg")


if __name__ == "__main__":
    main()
