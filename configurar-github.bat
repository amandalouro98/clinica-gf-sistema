@echo off
chcp 65001 >nul
title GitHub Setup - Clinica GF
color 0A

echo =========================================
echo   CONFIGURAR GITHUB - Clinica GF
echo =========================================
echo.
echo Este script vai configurar Git no seu computador
echo e enviar o codigo para o GitHub.
echo.
pause

cd /d "%~dp0"

echo.
echo [1/8] Verificando se Git esta instalado...
git --version > nul 2>&1
if errorlevel 1 (
    echo.
    echo ERRO: Git nao esta instalado!
    echo.
    echo Baixe e instale o Git:
    echo https://git-scm.com/download/win
    echo.
    echo Depois de instalar, execute este script novamente.
    pause
    exit /b 1
)
echo OK: Git encontrado!

echo.
echo [2/8] Configurando Git...
echo.
set /p GIT_NAME="Digite seu nome completo: "
set /p GIT_EMAIL="Digite seu email (amandalouromo@gmail.com): "

git config --global user.name "%GIT_NAME%"
git config --global user.email "%GIT_EMAIL%"
git config --global credential.helper cache
git config --global init.defaultBranch main

echo.
echo [3/8] Inicializando repositorio...
git init

echo.
echo [4/8] Adicionando arquivos...
git add .

echo.
echo [5/8] Criando primeiro commit...
git commit -m "Primeira versao do sistema - Clinica Gabriela Franco"

echo.
echo [6/8] Configurando conexao com GitHub...
echo.
echo IMPORTANTE: Crie o repositorio no GitHub primeiro!
echo.
echo 1. Acesse: https://github.com/new
echo 2. Nome: clinica-gf-sistema
echo 3. Marque "Private"
echo 4. NAO marque README nem .gitignore
echo 5. Clique "Create repository"
echo.
pause

echo.
set /p GITHUB_USER="Digite seu usuario do GitHub: "

git remote add origin https://github.com/%GITHUB_USER%/clinica-gf-sistema.git

echo.
echo [7/8] Enviando para GitHub...
git push -u origin main

echo.
echo [8/8] Verificando...
git status

echo.
echo =========================================
echo   CONFIGURACAO CONCLUIDA!
echo =========================================
echo.
echo Seu codigo esta no GitHub!
echo.
echo Proximos passos:
echo 1. Configure os Secrets no GitHub (Settings -> Secrets)
echo 2. Contrate o VPS na Locaweb
echo 3. Siga o guia GITHUB-VPS-GUIA-COMPLETO.md
echo.
pause
