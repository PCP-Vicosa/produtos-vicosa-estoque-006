#!/usr/bin/env python3
"""
consolidar_extracoes.py
-----------------------
Monta o BD_006.xlsx empilhado a partir da pasta de extracoes diarias e
arquiva a extracao do dia do Deposito 022.

Pastas de trabalho:
    data/extracoes/006/   -> uma extracao por dia do Deposito 006
    data/extracoes/022/   -> uma extracao por dia do Deposito 022

O nome do arquivo nao importa: a data usada e a da coluna "Data Estoque"
(no 006) e a data de modificacao do arquivo (no 022). Se o mesmo dia
aparecer em dois arquivos, vale o mais recente.

Uso:
    python scripts/consolidar_extracoes.py
"""
import shutil
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

DATA_DIR = BASE_DIR / "data"
EXTR_006 = DATA_DIR / "extracoes" / "006"
EXTR_022 = DATA_DIR / "extracoes" / "022"
BD_006 = DATA_DIR / "BD_006.xlsx"
BD_022 = DATA_DIR / "estoque-022" / "BD_022.xlsx"
HIST_022 = DATA_DIR / "estoque-022" / "historico"

from build_estoque_022 import ler_excel_robusto  # noqa: E402


def consolidar_006() -> bool:
    arquivos = sorted(p for p in EXTR_006.glob("*.xls*") if not p.name.startswith("~$"))
    if not arquivos:
        print(f"[006] Nenhuma extracao em {EXTR_006}. Nada a consolidar.")
        return False

    partes = []
    for p in arquivos:
        try:
            df = ler_excel_robusto(p)
        except Exception as e:
            print(f"[006] [ERRO] nao foi possivel ler {p.name}: {e}")
            continue
        if "Data Estoque" not in df.columns:
            print(f"[006] [ERRO] {p.name} nao tem a coluna 'Data Estoque'. Ignorado.")
            continue
        df["Data Estoque"] = pd.to_datetime(df["Data Estoque"], errors="coerce")
        df["_origem"] = p.name
        df["_mtime"] = p.stat().st_mtime
        partes.append(df)
        dias = df["Data Estoque"].dt.normalize().dropna().unique()
        print(f"[006] {p.name}: {len(df)} linhas, "
              f"{len(dias)} dia(s) ({pd.Timestamp(min(dias)):%d/%m} a "
              f"{pd.Timestamp(max(dias)):%d/%m})")

    if not partes:
        return False

    df = pd.concat(partes, ignore_index=True)

    # Mesmo dia em dois arquivos: fica o arquivo mais recente.
    dono = (df.groupby(df["Data Estoque"].dt.normalize())["_mtime"]
              .max().rename("_vencedor"))
    df = df.join(dono, on=df["Data Estoque"].dt.normalize())
    descartadas = int((df["_mtime"] != df["_vencedor"]).sum())
    if descartadas:
        print(f"[006] {descartadas} linha(s) descartadas por haver extracao "
              f"mais recente para o mesmo dia.")
    df = df[df["_mtime"] == df["_vencedor"]].drop(columns=["_mtime", "_vencedor", "_origem"])

    df = (df.drop_duplicates(subset=["Data Estoque", "Lote Fab.", "Produto"])
            .sort_values(["Data Estoque", "Produto", "Lote Fab."])
            .reset_index(drop=True))

    dias = sorted(df["Data Estoque"].dt.normalize().dropna().unique())
    faltando = []
    if len(dias) >= 2:
        todos = pd.date_range(dias[0], dias[-1], freq="D")
        faltando = [d for d in todos if d not in set(dias) and d.weekday() < 6]

    if BD_006.exists():
        shutil.copy2(BD_006, BD_006.with_suffix(".xlsx.bak"))
    df.to_excel(BD_006, index=False)

    print(f"\n[006] BD_006.xlsx regravado: {len(df)} linhas, {len(dias)} dia(s), "
          f"de {pd.Timestamp(dias[0]):%d/%m/%Y} a {pd.Timestamp(dias[-1]):%d/%m/%Y}.")
    if faltando:
        print(f"[006] [AVISO] {len(faltando)} dia(s) uteis sem extracao: "
              + ", ".join(f"{d:%d/%m}" for d in faltando))
    return True


def arquivar_022() -> bool:
    arquivos = sorted(p for p in EXTR_022.glob("*.xls*") if not p.name.startswith("~$"))
    if not arquivos:
        print(f"\n[022] Nenhuma extracao em {EXTR_022}. Nada a arquivar.")
        return False

    HIST_022.mkdir(parents=True, exist_ok=True)
    mais_recente = max(arquivos, key=lambda p: p.stat().st_mtime)

    for p in arquivos:
        data = (pd.Timestamp(p.stat().st_mtime, unit="s", tz="UTC")
                  .tz_convert("America/Sao_Paulo").strftime("%Y-%m-%d"))
        destino = HIST_022 / f"BD_022_{data}.xlsx"
        shutil.copy2(p, destino)
        print(f"[022] {p.name} -> historico/{destino.name}")

    BD_022.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(mais_recente, BD_022)
    print(f"[022] BD_022.xlsx atualizado com {mais_recente.name}.")
    print(f"[022] Historico acumulado: {len(list(HIST_022.glob('BD_022_*.xlsx')))} dia(s).")
    return True


def main():
    print("=" * 66)
    print("CONSOLIDACAO DAS EXTRACOES DIARIAS")
    print("=" * 66)
    EXTR_006.mkdir(parents=True, exist_ok=True)
    EXTR_022.mkdir(parents=True, exist_ok=True)
    a = consolidar_006()
    b = arquivar_022()
    if a or b:
        print("\nProximo passo: python scripts/build_all.py")
    print("=" * 66)


if __name__ == "__main__":
    main()
