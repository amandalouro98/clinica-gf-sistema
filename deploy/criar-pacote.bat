@echo off
chcp 65001 >nul
title Deploy VPS - Gabriela Franco Sistemas
color 0B

echo =========================================
echo   DEPLOY VPS - Gabriela Franco
echo =========================================
echo.
echo Este script vai preparar os arquivos para envio ao VPS.
echo.
pause

cd /d "%~dp0.."
set "PROJECT_DIR=%CD%"
set "DEPLOY_DIR=%PROJECT_DIR%\deploy"

echo.
echo [1/5] Verificando arquivos...
echo.

if not exist "%PROJECT_DIR%\app.py" (
    echo ERRO: Arquivo app.py nao encontrado!
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%\Dockerfile" (
    echo ERRO: Dockerfile nao encontrado!
    pause
    exit /b 1
)

echo [2/5] Criando pacote de deploy...
echo.

rem Criar pasta temporaria
set "TEMP_DIR=%TEMP%\clinica-gf-deploy"
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

rem Copiar arquivos essenciais
echo Copiando arquivos...
xcopy "%PROJECT_DIR%\app.py" "%TEMP_DIR%\" /Y >nul
xcopy "%PROJECT_DIR%\*.py" "%TEMP_DIR%\" /Y >nul 2>nul
xcopy "%PROJECT_DIR%\Dockerfile" "%TEMP_DIR%\" /Y >nul
xcopy "%PROJECT_DIR%\docker-compose.yml" "%TEMP_DIR%\" /Y >nul
xcopy "%PROJECT_DIR%\nginx.conf" "%TEMP_DIR%\" /Y >nul
xcopy "%PROJECT_DIR%\requirements.txt" "%TEMP_DIR%\" /Y >nul
xcopy "%PROJECT_DIR%\.env.example" "%TEMP_DIR%\" /Y >nul

rem Copiar pastas
echo Copiando pastas...
xcopy "%PROJECT_DIR%\models" "%TEMP_DIR%\models\" /E /I /Y >nul
xcopy "%PROJECT_DIR%\utils" "%TEMP_DIR%\utils\" /E /I /Y >nul
xcopy "%PROJECT_DIR%\services" "%TEMP_DIR%\services\" /E /I /Y >nul
xcopy "%PROJECT_DIR%\deploy" "%TEMP_DIR%\deploy\" /E /I /Y >nul

echo.
echo [3/5] Criando arquivo ZIP...
echo.

powershell -Command "Compress-Archive -Path '%TEMP_DIR%\*' -DestinationPath '%DEPLOY_DIR%\clinica-gf-vps.zip' -Force"

echo [4/5] Limpando arquivos temporarios...
rmdir /s /q "%TEMP_DIR%"

echo.
echo =========================================
echo   PACOTE CRIADO COM SUCESSO!
echo =========================================
echo.
echo Arquivo: %DEPLOY_DIR%\clinica-gf-vps.zip
echo.
echo Proximos passos:
echo 1. Envie este arquivo ZIP para o VPS
echo 2. Extraia em /opt/clinica-gf
echo 3. Siga o guia em deploy\GUIA-DEPLOY.md
echo.
echo Comando para enviar via SCP:
echo scp %DEPLOY_DIR%\clinica-gf-vps.zip root@IP_DO_VPS:/opt/
echo.
pause
