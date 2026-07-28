#!/usr/bin/env python3
"""
auto_git_sync.py
-----------------
Fica rodando em segundo plano observando o repositório. Sempre que detecta
alguma mudança (arquivo criado, editado ou removido) e a pasta fica "parada"
por alguns segundos (sem novas alterações), roda automaticamente:

    git add .
    git commit -m "Atualização automática - <data/hora>"
    git push

Como usar (dentro do VSCode):
    1. Abra um terminal no VSCode (Terminal > New Terminal).
    2. Rode:  python scripts/auto_git_sync.py
    3. Deixe esse terminal aberto. A partir daí, qualquer alteração salva
       no projeto é enviada pro GitHub automaticamente.
    4. Para parar, clique no terminal e aperte Ctrl+C.

Também dá pra rodar como Task do VSCode (veja .vscode/tasks.json ->
"Git Auto Sync").
"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent

# Quanto tempo (em segundos) esperar sem nenhuma mudança nova antes de
# efetivamente commitar. Evita ficar commitando no meio de uma edição.
TEMPO_ESTAVEL = 5

# De quanto em quanto tempo (em segundos) checar se há mudanças.
INTERVALO_VERIFICACAO = 2


def rodar(cmd):
    return subprocess.run(
        cmd, cwd=REPO_DIR, capture_output=True, text=True, shell=False
    )


def estado_atual():
    """Retorna a lista de arquivos alterados (texto). Vazio = nada a enviar.

    Devolvemos o conteudo, e nao so um sim/nao, porque a estabilidade precisa
    ser medida sobre "o que mudou". Comparar apenas "existe mudanca?" fazia o
    contador reiniciar a cada verificacao e o commit nunca acontecia.
    """
    r = rodar(["git", "status", "--porcelain"])
    return r.stdout.strip()


def sincronizar():
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    print(f"[{agora}] Alterações detectadas e estáveis. Sincronizando com o GitHub...")

    add = rodar(["git", "add", "."])
    if add.returncode != 0:
        print(f"  Erro no 'git add': {add.stderr.strip()}")
        return

    msg = f"Atualização automática - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    commit = rodar(["git", "commit", "-m", msg])
    if commit.returncode != 0:
        # Pode ser "nothing to commit" se outra rotina já commitou nesse meio-tempo.
        if "nothing to commit" in (commit.stdout + commit.stderr).lower():
            print("  Nada para commitar (já estava tudo salvo).")
            return
        print(f"  Erro no 'git commit': {commit.stderr.strip() or commit.stdout.strip()}")
        return

    push = rodar(["git", "push"])
    if push.returncode != 0:
        print(f"  Erro no 'git push': {push.stderr.strip()}")
        print("  As mudanças foram commitadas localmente, mas não foram enviadas ao GitHub.")
        print("  Verifique sua conexão / autenticação e rode 'git push' manualmente se precisar.")
        return

    print(f"  Pronto! Alterações enviadas ao GitHub ({msg}).")


def main():
    print("=" * 60)
    print(" Git Auto Sync - Viçosa BI")
    print(f" Pasta monitorada: {REPO_DIR}")
    print(f" Verificando a cada {INTERVALO_VERIFICACAO}s | ")
    print(f" Aguarda {TEMPO_ESTAVEL}s de estabilidade antes de enviar")
    print(" Pressione Ctrl+C para parar.")
    print("=" * 60)

    # Confere se está mesmo dentro de um repositório git.
    check = rodar(["git", "rev-parse", "--is-inside-work-tree"])
    if check.returncode != 0:
        print("Erro: esta pasta não é um repositório git. Rode 'git init' primeiro.")
        sys.exit(1)

    estado_anterior = ""
    marcado_em = None

    try:
        while True:
            estado = estado_atual()

            if not estado:
                # Arvore limpa: nada pendente.
                estado_anterior, marcado_em = "", None
            elif estado != estado_anterior:
                # A lista de arquivos alterados mudou desde a ultima checagem:
                # ainda esta sendo mexido. Reinicia a contagem.
                estado_anterior = estado
                marcado_em = time.time()
                n = len(estado.splitlines())
                print(f"Mudança detectada ({n} arquivo(s)), aguardando estabilizar...")
            elif marcado_em is not None and time.time() - marcado_em >= TEMPO_ESTAVEL:
                # Mesma lista ha TEMPO_ESTAVEL segundos: pode enviar.
                sincronizar()
                estado_anterior, marcado_em = "", None

            time.sleep(INTERVALO_VERIFICACAO)
    except KeyboardInterrupt:
        print("\nGit Auto Sync encerrado.")


if __name__ == "__main__":
    main()
