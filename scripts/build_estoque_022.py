#!/usr/bin/env python3
"""
build_estoque_022.py
---------------------
Lê a base BD_022.xlsx (snapshot único do Depósito 022 — produtos aguardando
liberação da qualidade) e gera o dashboard estático docs/estoque-022/index.html.

Diferente do Estoque 006, o BD_022.xlsx não é um histórico empilhado dia a
dia: é sobrescrito diariamente (ou quando necessário) com a foto atual do
depósito. Por isso não há filtro de data — a página mostra sempre a leitura
mais recente do arquivo, com a data de atualização exibida como texto.

Uso:
    python scripts/build_estoque_022.py

Arquivos de entrada (pasta data/):
    estoque-022/BD_022.xlsx      - snapshot atual do Depósito 022
    Dim_Peso_Produto.csv         - peso (kg) por unidade de cada produto (compartilhado com o Estoque 006)
    Dim_Nome_Curto_Produto.csv   - nome comercial curto de cada produto (compartilhado com o Estoque 006)
    Tema.json                    - tema de cores exportado do Power BI (compartilhado, opcional)

Saída:
    docs/estoque-022/index.html
"""
import json
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BD_PATH = DATA_DIR / "estoque-022" / "BD_022.xlsx"
BD_006_PATH = DATA_DIR / "BD_006.xlsx"
PESO_PATH = DATA_DIR / "Dim_Peso_Produto.csv"
NOME_PATH = DATA_DIR / "Dim_Nome_Curto_Produto.csv"
OUTPUT_PATH = BASE_DIR / "docs" / "estoque-022" / "index.html"
TEMPLATE_PATH = BASE_DIR / "scripts" / "template_estoque022.html"

# Código da Família -> nome do Setor (mesmo mapeamento do Estoque 006).
SETOR_POR_FAMILIA = {
    "003": "Iogurte",
    "005": "Doce",
    "006": "Manteiga",
    "007": "Queijo",
    "008": "Leite",
    "009": "Requeijão",
}


def ler_excel_robusto(path: Path) -> pd.DataFrame:
    """Lê um .xlsx exportado do SAP, que às vezes vem com o zip interno
    usando '\\' como separador (quebra o openpyxl) e/ou com estilos que o
    openpyxl não consegue interpretar. Tenta a leitura direta primeiro e,
    se falhar, corrige o zip e, em último caso, converte via LibreOffice
    headless antes de ler."""
    try:
        return pd.read_excel(path, sheet_name=0, header=0)
    except Exception:
        pass

    # 1) Corrige separadores de caminho dentro do zip (\ -> /)
    with tempfile.TemporaryDirectory() as tmp:
        src_dir = Path(tmp) / "src"
        src_dir.mkdir()
        corrigido = src_dir / "corrigido.xlsx"
        with zipfile.ZipFile(path, "r") as zin:
            with zipfile.ZipFile(corrigido, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    dados = zin.read(item.filename)
                    zout.writestr(item.filename.replace("\\", "/"), dados)
        try:
            return pd.read_excel(corrigido, sheet_name=0, header=0)
        except Exception:
            pass

        # 2) Ainda falhou (estilos incompatíveis) -> converte via LibreOffice.
        # Usa uma pasta de saída DIFERENTE da de entrada: o LibreOffice falha
        # silenciosamente ao tentar sobrescrever o arquivo de origem no lugar.
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            raise RuntimeError(
                "Não foi possível ler o BD_022.xlsx e o LibreOffice não está "
                "disponível para converter o arquivo."
            )
        out_dir = Path(tmp) / "out"
        out_dir.mkdir()
        subprocess.run(
            [soffice, "--headless", "--convert-to",
             "xlsx:Calc MS Excel 2007 XML", str(corrigido), "--outdir", str(out_dir)],
            check=True, capture_output=True, timeout=120,
        )
        convertido = out_dir / "corrigido.xlsx"
        return pd.read_excel(convertido, sheet_name=0, header=0)


def carregar_dimensoes():
    peso = pd.read_csv(PESO_PATH, sep=";", decimal=",", dtype={"Produto": str})
    peso["Produto"] = peso["Produto"].str.zfill(10)
    peso = peso.set_index("Produto")["Gramatura_KG"]

    nomes = pd.read_csv(NOME_PATH, sep=";", dtype={"Produto": str})
    nomes["Produto"] = nomes["Produto"].str.zfill(10)
    nomes = nomes.set_index("Produto")["Nome_Curto"]

    return peso, nomes


def nome_produto_fallback(descricao) -> str:
    if not isinstance(descricao, str):
        return "Produto sem nome"
    return descricao.split(" - ")[0].strip()


def fmt_data(d):
    return pd.Timestamp(d).strftime("%d/%m/%Y") if pd.notna(d) else None


def _mtime_local(caminho: Path) -> pd.Timestamp:
    return (pd.Timestamp(caminho.stat().st_mtime, unit="s", tz="UTC")
            .tz_convert("America/Sao_Paulo"))


def data_da_extracao() -> str:
    """Data que aparece no cabecalho como 'Atualizado em'.

    O BD_022 e uma foto instantanea: nao tem coluna de data dentro dele, entao
    a unica pista e o arquivo. Antes olhavamos so o mtime do BD_022.xlsx, o que
    mentia quando a copia preservava o horario original (shutil.copy2) — o
    painel dizia 25/07 depois de uma extracao feita hoje. Agora vale o mais
    recente entre o BD_022.xlsx e a ultima extracao solta em data/extracoes/022.
    """
    candidatos = []
    if BD_PATH.exists():
        candidatos.append(("BD_022.xlsx", _mtime_local(BD_PATH)))

    pasta = DATA_DIR / "extracoes" / "022"
    if pasta.exists():
        for f in pasta.glob("*.xls*"):
            if not f.name.startswith("~$"):
                candidatos.append((f.name, _mtime_local(f)))

    if not candidatos:
        return pd.Timestamp.now(tz="America/Sao_Paulo").strftime("%d/%m/%Y")

    nome, ts = max(candidatos, key=lambda c: c[1])
    hoje = pd.Timestamp.now(tz="America/Sao_Paulo").normalize()
    dias = (hoje - ts.normalize()).days
    print(f"Data da extracao: {ts:%d/%m/%Y %H:%M} (origem: {nome})")
    if dias >= 1:
        print(f"[AVISO] a extracao mais recente tem {dias} dia(s). Se voce "
              f"exportou hoje, o arquivo novo nao chegou em data/estoque-022/ "
              f"nem em data/extracoes/022/.")
    return ts.strftime("%d/%m/%Y")


def carregar_dados() -> pd.DataFrame:
    df = ler_excel_robusto(BD_PATH)

    colunas_esperadas = [
        "Família", "Lote Fab.", "Produto", "Saldo Lote",
        "Data Validade", "Data Fab. Lote", "Descrição Produto",
    ]
    faltando = [c for c in colunas_esperadas if c not in df.columns]
    if faltando:
        raise ValueError(
            f"As colunas a seguir não foram encontradas no BD_022.xlsx: {faltando}. "
            f"Colunas disponíveis: {list(df.columns)}"
        )

    df = df.copy()
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
    df = df[df["Saldo Lote"] > 0]

    return df


def conferir_contra_006(df: pd.DataFrame, data_arquivo: str) -> tuple[pd.DataFrame, dict]:
    """Compara o snapshot do Depósito 022 com o último snapshot do Depósito 006.

    O BD_022.xlsx é sobrescrito manualmente e, quando isso não é feito no mesmo
    dia da extração do BD_006, os lotes que já foram liberados pela qualidade
    continuam listados aqui — passando a ser contados nos dois painéis ao mesmo
    tempo. Um lote que aparece no 006 na data mais recente já saiu da qualidade
    por definição, então ele é removido deste painel e o fato é registrado para
    ser comunicado na página.

    Retorna o DataFrame já limpo e o dicionário de alerta para o payload.
    """
    alerta = {"dias_defasagem": 0, "data_006": None,
              "lotes_removidos": 0, "kg_removidos": 0.0}

    if not BD_006_PATH.exists():
        print("[aviso] BD_006.xlsx não encontrado — a conferência entre os "
              "depósitos foi pulada.")
        return df, alerta

    d6 = pd.read_excel(BD_006_PATH, usecols=["Data Estoque", "Lote Fab."])
    d6["Data Estoque"] = pd.to_datetime(d6["Data Estoque"], errors="coerce")
    ultima = d6["Data Estoque"].max()
    if pd.isna(ultima):
        return df, alerta

    alerta["data_006"] = ultima.strftime("%d/%m/%Y")
    data_022 = pd.to_datetime(data_arquivo, format="%d/%m/%Y")
    alerta["dias_defasagem"] = max(0, (ultima.normalize() - data_022.normalize()).days)

    lotes_006 = set(d6.loc[d6["Data Estoque"] == ultima, "Lote Fab."].astype(str))
    ja_liberados = df["Lote Fab."].astype(str).isin(lotes_006)

    if ja_liberados.any():
        alerta["lotes_removidos"] = int(ja_liberados.sum())
        alerta["kg_removidos"] = round(float(df.loc[ja_liberados, "Saldo KG"].sum()), 2)
        print(f"[ALERTA] {alerta['lotes_removidos']} lote(s) do BD_022 já constam no "
              f"Depósito 006 de {alerta['data_006']} ({alerta['kg_removidos']:,.2f} kg). "
              f"Foram removidos deste painel para não haver contagem em duplicidade.")
        df = df[~ja_liberados]

    if alerta["dias_defasagem"] > 0:
        print(f"[ALERTA] O BD_022.xlsx é de {data_arquivo} e o BD_006 já está em "
              f"{alerta['data_006']} — defasagem de {alerta['dias_defasagem']} dia(s). "
              f"Exporte o BD_022 novamente.")

    return df, alerta


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
    return {"setores": setores, "produtos": produtos_lista}


def montar_lotes(df: pd.DataFrame) -> list:
    linhas = []
    for _, row in df.iterrows():
        vida_total = (
            (row["Data Validade"] - row["Data Fab. Lote"]).days
            if pd.notna(row["Data Validade"]) and pd.notna(row["Data Fab. Lote"])
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
        })
    return linhas


def gerar_html(payload: dict, tema: dict | None) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__ESTOQUE022_DATA__", json.dumps(payload, ensure_ascii=False))
    html = html.replace("__THEME_DATA__", json.dumps(tema or {}, ensure_ascii=False))
    return html


def main():
    if not BD_PATH.exists():
        raise SystemExit(f"Não encontrei {BD_PATH}. Copie o BD_022.xlsx para data/estoque-022/.")
    if not PESO_PATH.exists() or not NOME_PATH.exists():
        raise SystemExit(
            "Faltam Dim_Peso_Produto.csv e/ou Dim_Nome_Curto_Produto.csv na pasta data/."
        )

    df = carregar_dados()

    tema = None
    tema_path = DATA_DIR / "Tema.json"
    if tema_path.exists():
        tema = json.loads(tema_path.read_text(encoding="utf-8-sig"))

    data_arquivo = data_da_extracao()

    df, alerta = conferir_contra_006(df, data_arquivo)

    payload = {
        "gerado_em": pd.Timestamp.now(tz="America/Sao_Paulo").strftime("%d/%m/%Y %H:%M"),
        "data_arquivo": data_arquivo,
        "alerta": alerta,
        "filtros": montar_filtros(df),
        "lotes": montar_lotes(df),
    }

    html = gerar_html(payload, tema)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")

    print(f"Dashboard gerado em: {OUTPUT_PATH}")
    print(f"Lotes aguardando liberação: {len(payload['lotes'])} | Data do arquivo: {data_arquivo}")


if __name__ == "__main__":
    main()
