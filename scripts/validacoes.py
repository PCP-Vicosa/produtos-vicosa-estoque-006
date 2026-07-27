#!/usr/bin/env python3
"""
validacoes.py
--------------
Camada de verificação das bases, executada ANTES de gerar as páginas.

O objetivo é simples: uma base incompleta ou incoerente nunca deve virar um
número errado publicado no site. Cada verificação devolve um resultado com
severidade:

    ERRO  -> impede a publicação (o build_all encerra sem gerar nada)
    AVISO -> gera a página, mas o problema é impresso em destaque

Uso:
    from validacoes import validar_tudo
    problemas = validar_tudo()
"""
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

BD_006 = DATA_DIR / "BD_006.xlsx"
BD_022 = DATA_DIR / "estoque-022" / "BD_022.xlsx"
ADERENCIA = DATA_DIR / "aderencia" / "Producao_Semanal_PowerBI.xlsx"
DIM_PESO = DATA_DIR / "Dim_Peso_Produto.csv"
DIM_NOME = DATA_DIR / "Dim_Nome_Curto_Produto.csv"
DE_PARA = DATA_DIR / "Dim_DePara_Produto.csv"

# Variação diária de saldo acima disto é tratada como suspeita de extração
# incompleta (em uma fábrica em operação normal o estoque não muda tanto de
# um dia para o outro).
VARIACAO_DIARIA_SUSPEITA = 0.40


class Problema:
    def __init__(self, severidade: str, base: str, mensagem: str):
        self.severidade = severidade  # "ERRO" ou "AVISO"
        self.base = base
        self.mensagem = mensagem

    def __str__(self):
        return f"[{self.severidade}] {self.base}: {self.mensagem}"


def _erro(base, msg):
    return Problema("ERRO", base, msg)


def _aviso(base, msg):
    return Problema("AVISO", base, msg)


def _carregar_dimensoes():
    peso = pd.read_csv(DIM_PESO, sep=";", decimal=",", dtype={"Produto": str})
    peso["Produto"] = peso["Produto"].str.zfill(10)
    nome = pd.read_csv(DIM_NOME, sep=";", dtype={"Produto": str})
    nome["Produto"] = nome["Produto"].str.zfill(10)
    return peso, nome


def validar_estoque_006() -> list:
    problemas = []
    if not BD_006.exists():
        return [_erro("BD_006", "arquivo não encontrado.")]

    df = pd.read_excel(BD_006)
    if df.empty:
        return [_erro("BD_006", "a planilha está vazia.")]

    obrigatorias = ["Data Estoque", "Família", "Lote Fab.", "Produto",
                    "Saldo Lote", "Data Validade", "Data Fab. Lote",
                    "Descrição Produto"]
    faltando = [c for c in obrigatorias if c not in df.columns]
    if faltando:
        return [_erro("BD_006", f"colunas obrigatórias ausentes: {faltando}.")]

    df["Data Estoque"] = pd.to_datetime(df["Data Estoque"], errors="coerce")
    df["Data Validade"] = pd.to_datetime(df["Data Validade"], errors="coerce")
    df["Data Fab. Lote"] = pd.to_datetime(df["Data Fab. Lote"], errors="coerce")
    df["Saldo Lote"] = pd.to_numeric(df["Saldo Lote"], errors="coerce")
    df["Produto Cod"] = df["Produto"].astype(str).str.zfill(10)

    sem_data = df["Data Estoque"].isna().sum()
    if sem_data:
        problemas.append(_erro("BD_006", f"{sem_data} linha(s) sem Data Estoque."))

    sem_saldo = df["Saldo Lote"].isna().sum()
    if sem_saldo:
        problemas.append(_erro("BD_006", f"{sem_saldo} linha(s) com Saldo Lote não numérico."))

    # Validade anterior à fabricação = erro de cadastro na origem.
    invertidas = (df["Data Validade"] < df["Data Fab. Lote"]).sum()
    if invertidas:
        problemas.append(_erro("BD_006",
                               f"{invertidas} lote(s) com Data Validade anterior à "
                               f"Data Fab. Lote — erro de cadastro na extração."))

    # Duplicidade exata: mesma data + mesmo lote + mesmo produto aparecendo
    # duas vezes indica consolidação feita duas vezes.
    dup = df.duplicated(subset=["Data Estoque", "Lote Fab.", "Produto"]).sum()
    if dup:
        problemas.append(_erro("BD_006",
                               f"{dup} linha(s) duplicadas (mesma data + lote + produto). "
                               f"Provável consolidação repetida do mesmo dia."))

    # Toda gramatura precisa existir, senão o SKU some do gráfico em silêncio.
    peso, nome = _carregar_dimensoes()
    sem_peso = sorted(set(df["Produto Cod"]) - set(peso["Produto"]))
    if sem_peso:
        problemas.append(_erro("BD_006",
                               f"{len(sem_peso)} produto(s) sem gramatura em "
                               f"Dim_Peso_Produto.csv: {sem_peso[:5]}. "
                               f"Eles apareceriam como 0 kg no painel."))
    sem_nome = sorted(set(df["Produto Cod"]) - set(nome["Produto"]))
    if sem_nome:
        problemas.append(_aviso("BD_006",
                                f"{len(sem_nome)} produto(s) sem nome curto: {sem_nome[:5]}. "
                                f"Será usada a descrição do SAP."))

    # Continuidade e coerência da série.
    dias = sorted(d for d in df["Data Estoque"].dropna().unique())
    if len(dias) < 2:
        problemas.append(_aviso("BD_006", "a série tem menos de 2 dias — "
                                          "nenhuma comparação diária é possível."))
    else:
        gram = df["Produto Cod"].map(peso.set_index("Produto")["Gramatura_KG"]).fillna(0)
        df["kg"] = df["Saldo Lote"].fillna(0) * gram
        por_dia = df.groupby("Data Estoque")["kg"].sum()
        anterior = None
        for dia, kg in por_dia.items():
            if anterior is not None and anterior > 0:
                var = abs(kg - anterior) / anterior
                if var > VARIACAO_DIARIA_SUSPEITA:
                    problemas.append(_aviso(
                        "BD_006",
                        f"o saldo de {dia:%d/%m/%Y} variou {var:.0%} em relação ao "
                        f"snapshot anterior ({anterior:,.0f} kg -> {kg:,.0f} kg). "
                        f"Confira se a extração daquele dia veio completa."))
            anterior = kg

        ultimo = pd.Timestamp(dias[-1])
        atraso = (pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).normalize()
                  - ultimo.normalize()).days
        if atraso > 1:
            problemas.append(_aviso("BD_006",
                                    f"o snapshot mais recente é de {ultimo:%d/%m/%Y}, "
                                    f"há {atraso} dias. A base pode estar desatualizada."))

    return problemas


def validar_estoque_022() -> list:
    problemas = []
    if not BD_022.exists():
        return [_erro("BD_022", "arquivo não encontrado.")]

    # A leitura robusta vive no build; aqui só checamos data e coerência.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_estoque_022 import ler_excel_robusto

    try:
        df = ler_excel_robusto(BD_022)
    except Exception as e:
        # Arquivo exportado pelo SAP com defeito interno. O conserto automático
        # depende do LibreOffice, que pode não existir na máquina. Isso impede
        # apenas o painel 022 — os outros dois continuam podendo ser gerados,
        # por isso é AVISO e não ERRO.
        return [_aviso("BD_022",
                       f"não foi possível ler o arquivo ({e}). SOLUÇÃO: abra o "
                       f"BD_022.xlsx no Excel e use Salvar como > Pasta de "
                       f"Trabalho do Excel (.xlsx), no mesmo local e com o mesmo "
                       f"nome. O painel do 022 não será atualizado até isso ser "
                       f"feito; os outros dois painéis seguem normalmente.")]

    if df.empty:
        return [_erro("BD_022", "a planilha está vazia.")]

    data_022 = (pd.Timestamp(BD_022.stat().st_mtime, unit="s", tz="UTC")
                .tz_convert("America/Sao_Paulo").normalize().tz_localize(None))

    if BD_006.exists():
        d6 = pd.read_excel(BD_006, usecols=["Data Estoque", "Lote Fab."])
        d6["Data Estoque"] = pd.to_datetime(d6["Data Estoque"], errors="coerce")
        ultima = d6["Data Estoque"].max()
        if pd.notna(ultima):
            defasagem = (ultima.normalize() - data_022).days
            if defasagem > 0:
                problemas.append(_aviso(
                    "BD_022",
                    f"a base é de {data_022:%d/%m/%Y} e o BD_006 já está em "
                    f"{ultima:%d/%m/%Y} — defasagem de {defasagem} dia(s). "
                    f"Os lotes já liberados serão removidos do painel, mas o "
                    f"correto é exportar o BD_022 novamente."))
            lotes_006 = set(d6.loc[d6["Data Estoque"] == ultima, "Lote Fab."].astype(str))
            sobrepostos = df["Lote Fab."].astype(str).isin(lotes_006).sum()
            if sobrepostos:
                problemas.append(_aviso(
                    "BD_022",
                    f"{sobrepostos} de {len(df)} lote(s) já constam no Depósito 006 — "
                    f"seriam contados duas vezes se não fossem removidos."))
    return problemas


def validar_aderencia() -> list:
    problemas = []
    if not ADERENCIA.exists():
        return [_erro("Aderência", "arquivo não encontrado.")]

    try:
        df = pd.read_excel(ADERENCIA, sheet_name="Dados_Consolidados")
    except Exception as e:
        return [_erro("Aderência", f"não foi possível ler a aba Dados_Consolidados: {e}")]

    if df.empty:
        return [_erro("Aderência", "a aba Dados_Consolidados está vazia.")]

    # Colunas CRUAS: sem elas nada pode ser recalculado.
    cruas = ["Semana", "Nº Semana", "Data Início Semana", "Produto", "Setor",
             "Gramatura (KG)", "Programado (UN)", "Produzido (UN)", "Demanda (UN)"]
    faltando = [c for c in cruas if c not in df.columns]
    if faltando:
        return [_erro("Aderência", f"colunas cruas ausentes: {faltando}.")]

    for c in ["Gramatura (KG)", "Programado (UN)", "Produzido (UN)", "Demanda (UN)"]:
        vazias = pd.to_numeric(df[c], errors="coerce").isna().sum()
        if vazias:
            problemas.append(_aviso("Aderência",
                                    f"{vazias} linha(s) sem valor em '{c}' "
                                    f"(serão tratadas como 0)."))

    sem_gram = (pd.to_numeric(df["Gramatura (KG)"], errors="coerce").fillna(0) <= 0).sum()
    if sem_gram:
        problemas.append(_erro("Aderência",
                               f"{sem_gram} linha(s) com Gramatura (KG) zerada ou "
                               f"negativa — os valores em kg ficariam errados."))

    sem_data = pd.to_datetime(df["Data Início Semana"], errors="coerce").isna().sum()
    if sem_data:
        problemas.append(_aviso("Aderência",
                                f"{sem_data} linha(s) sem Data Início Semana — "
                                f"serão descartadas."))

    d = pd.to_datetime(df["Data Início Semana"], errors="coerce")
    ultima = d.max()
    if pd.notna(ultima):
        atraso = (pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None).normalize()
                  - ultima.normalize()).days
        if atraso > 14:
            problemas.append(_aviso("Aderência",
                                    f"a última semana registrada começa em "
                                    f"{ultima:%d/%m/%Y}, há {atraso} dias."))
    return problemas


def validar_de_para() -> list:
    """Todo nome de produto da aderência precisa existir no de-para, e todo
    código apontado precisa existir na dimensão de produto. Sem isso, um
    produto novo entraria na base e sumiria dos cruzamentos em silêncio."""
    problemas = []
    if not DE_PARA.exists():
        return [_aviso("De-Para", "Dim_DePara_Produto.csv não encontrado — "
                                  "nenhum cruzamento entre aderência e estoque é possível.")]
    if not ADERENCIA.exists():
        return problemas

    dp = pd.read_csv(DE_PARA, sep=";", dtype=str).fillna("")
    ad = pd.read_excel(ADERENCIA, sheet_name="Dados_Consolidados")
    nomes = set(ad["Produto"].dropna().astype(str))

    novos = sorted(nomes - set(dp["Produto_Aderencia"]))
    if novos:
        problemas.append(_erro("De-Para",
                               f"{len(novos)} produto(s) da aderência sem linha no "
                               f"de-para: {novos[:5]}. Cadastre o código SAP."))

    sem_cod = sorted(dp.loc[dp["Produto"].str.strip() == "", "Produto_Aderencia"])
    if sem_cod:
        problemas.append(_aviso("De-Para",
                                f"{len(sem_cod)} produto(s) sem código SAP "
                                f"(não existem no estoque): {sem_cod}."))

    if DIM_NOME.exists():
        validos = set(pd.read_csv(DIM_NOME, sep=";", dtype=str)["Produto"])
        maus = sorted(set(dp.loc[dp["Produto"].str.strip() != "", "Produto"]) - validos)
        if maus:
            problemas.append(_erro("De-Para",
                                   f"{len(maus)} código(s) do de-para não existem na "
                                   f"dimensão de produto: {maus[:5]}."))
    return problemas


def validar_tudo() -> list:
    problemas = []
    problemas += validar_estoque_006()
    problemas += validar_aderencia()
    problemas += validar_estoque_022()
    problemas += validar_de_para()
    return problemas


if __name__ == "__main__":
    for p in validar_tudo():
        print(p)
