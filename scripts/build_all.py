#!/usr/bin/env python3
"""
build_all.py
------------
Ponto unico de geracao do portal.

Sequencia:
    1. Valida as tres bases (validacoes.py)
    2. Se houver ERRO, encerra sem gerar nada
    3. Gera os tres paineis
    4. Imprime um resumo do que foi publicado

Uso:
    python scripts/build_all.py
    python scripts/build_all.py --ignorar-erros   (gera mesmo com ERRO)
"""
import subprocess
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from validacoes import validar_tudo, BD_006, DIM_PESO  # noqa: E402

PAINEIS = [
    ("Estoque 006", "build_dashboard.py"),
    ("Aderencia", "build_aderencia.py"),
    ("Estoque 022", "build_estoque_022.py"),
]


def _linha(titulo=""):
    if titulo:
        print(f"\n{'=' * 66}\n{titulo}\n{'=' * 66}")
    else:
        print("=" * 66)


def rodar_validacoes(ignorar_erros: bool) -> bool:
    _linha("1. VERIFICACAO DAS BASES")
    problemas = validar_tudo()
    erros = [p for p in problemas if p.severidade == "ERRO"]
    avisos = [p for p in problemas if p.severidade == "AVISO"]

    if not problemas:
        print("Nenhum problema encontrado. As tres bases estao consistentes.")
        return True

    for p in erros:
        print(f"  {p}")
    for p in avisos:
        print(f"  {p}")

    print(f"\nResultado: {len(erros)} erro(s), {len(avisos)} aviso(s).")

    if erros and not ignorar_erros:
        print("\nA geracao foi INTERROMPIDA. Corrija os erros acima e rode de novo.")
        print("Para gerar assim mesmo: python scripts/build_all.py --ignorar-erros")
        return False
    if erros:
        print("\n[--ignorar-erros] Gerando mesmo com erros. Confira os numeros.")
    return True


def gerar_paineis() -> bool:
    _linha("2. GERACAO DOS PAINEIS")
    ok = True
    for nome, script in PAINEIS:
        print(f"\n--- {nome} ---")
        r = subprocess.run([sys.executable, str(SCRIPTS / script)],
                           cwd=str(BASE_DIR))
        if r.returncode != 0:
            print(f"[ERRO] {nome} falhou (codigo {r.returncode}).")
            ok = False
    return ok


def resumo():
    _linha("3. RESUMO DO QUE FOI PUBLICADO")
    try:
        df = pd.read_excel(BD_006)
        peso = pd.read_csv(DIM_PESO, sep=";", decimal=",", dtype={"Produto": str})
        peso["Produto"] = peso["Produto"].str.zfill(10)
        gram = peso.set_index("Produto")["Gramatura_KG"]

        df["Data Estoque"] = pd.to_datetime(df["Data Estoque"], errors="coerce")
        df["kg"] = (pd.to_numeric(df["Saldo Lote"], errors="coerce").fillna(0)
                    * df["Produto"].astype(str).str.zfill(10).map(gram).fillna(0))

        por_dia = df.groupby("Data Estoque")["kg"].sum().sort_index()
        dias = len(por_dia)
        ultimo = por_dia.index[-1]
        atual = por_dia.iloc[-1]
        lotes = int((df["Data Estoque"] == ultimo).sum())
        skus = df.loc[df["Data Estoque"] == ultimo, "Produto"].nunique()

        var = ""
        if dias >= 2:
            ant = por_dia.iloc[-2]
            if ant:
                var = f" | variacao vs. dia anterior: {(atual - ant) / ant:+.1%}"

        kg_fmt = f"{atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        print(f"Estoque 006  : {dias} dia(s) de historico | ultimo snapshot "
              f"{ultimo:%d/%m/%Y}")
        print(f"               {lotes} lotes | {skus} SKUs | {kg_fmt} kg{var}")
    except Exception as e:
        print(f"[aviso] nao foi possivel montar o resumo do 006: {e}")

    print("\nPaginas geradas em docs/. Para publicar, no VS Code:")
    print('  git add . && git commit -m "atualiza bases" && git push')
    _linha()


def main():
    ignorar = "--ignorar-erros" in sys.argv
    if not rodar_validacoes(ignorar):
        sys.exit(1)
    if not gerar_paineis():
        sys.exit(1)
    resumo()


if __name__ == "__main__":
    main()
