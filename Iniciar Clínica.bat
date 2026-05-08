@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

REM Vai para a pasta onde o .bat está
cd /d "%~dp0"

REM 1) Garante que existe o ambiente virtual .venv
if not exist ".venv\Scripts\python.exe" (
  echo [INFO] Criando ambiente virtual .venv...
  py -3 -m venv .venv || python -m venv .venv
)

if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] Python nao encontrado ou falha ao criar .venv.
  echo Instale o Python 3 e tente novamente.
  pause
  exit /b 1
)

REM 2) Instala dependencias (apenas na primeira vez ou se faltar)
if not exist ".venv\installed.ok" (
  echo [INFO] Instalando dependencias...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto FAIL
  echo ok > ".venv\installed.ok"
)

REM 3) Inicia o sistema
if exist "launcher.py" (
  start "" ".venv\Scripts\pythonw.exe" launcher.py
) else (
  start "" ".venv\Scripts\pythonw.exe" -m streamlit run app.py
)
exit /b 0

:FAIL
echo [ERRO] Falha ao instalar dependencias. Veja as mensagens acima.
pause
exit /b 1