@echo off
REM Atalho para rodar o Git Auto Sync clicando duas vezes neste arquivo.
cd /d "%~dp0.."
python scripts\auto_git_sync.py
pause
