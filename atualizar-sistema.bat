@echo off
chcp 65001 >nul
title Atualizar Sistema - Clinica GF
color 0E

echo =========================================
echo   ATUALIZAR SISTEMA - Clinica GF
echo =========================================
echo.
echo Este script vai enviar suas alteracoes
echo para o GitHub.
echo.
pause

cd /d "%~dp0"

echo.
echo [1/4] Verificando alteracoes...
git status

echo.
echo [2/4] Adicionando alteracoes...
git add .

echo.
set /p MENSAGEM="Digite uma descricao das alteracoes: "

echo.
echo [3/4] Criando commit...
git commit -m "%MENSAGEM%"

echo.
echo [4/4] Enviando para GitHub...
git push

echo.
echo =========================================
echo   ATUALIZACAO CONCLUIDA!
echo =========================================
echo.
echo Seu codigo foi atualizado no GitHub!
echo.
echo Se configurou deploy automatico, o VPS
echo vai atualizar sozinho em alguns minutos.
echo.
echo Se nao, acesse o VPS e execute:
echo   cd /opt/clinica-gf
echo   git pull
echo   docker-compose up -d --build
echo.
pause
