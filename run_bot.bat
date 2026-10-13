@echo off
title Pull and Bear Restock Bot
chcp 65001 > nul
cls

:menu
cls
echo ============================================================
echo           PULL ^& BEAR RESTOCK ^& AUTO-BUY BOT
echo ============================================================
echo   Prenda: Cardigan Dickies (07563305) ^| Talla: XS
echo ============================================================
echo.
echo   [1] Iniciar el Bot (Modo Normal / Visual)
echo   [2] Iniciar el Bot en Segundo Plano (Sin ventana)
echo   [3] Configurar Telegram y Opciones (Asistente)
echo   [4] Probar Alertas, Sonido y Telegram (Test)
echo   [5] Salir
echo.
set /p opcion="Selecciona una opción [1-5]: "

if "%opcion%"=="1" goto start_normal
if "%opcion%"=="2" goto start_headless
if "%opcion%"=="3" goto config
if "%opcion%"=="4" goto test_alert
if "%opcion%"=="5" exit

echo Opción no válida.
timeout /t 2 > nul
goto menu

:start_normal
cls
echo Iniciando el Bot de Pull^&Bear (Modo Visual)...
echo.
py bot.py
pause
goto menu

:start_headless
cls
echo Iniciando el Bot de Pull^&Bear (Segundo Plano)...
echo Puedes minimizar esta consola mientras trabaja.
echo.
py -c "import json; c=json.load(open('config.json', encoding='utf-8')); c['headless']=True; json.dump(c, open('config.json', 'w', encoding='utf-8'), indent=2)"
py bot.py
pause
goto menu

:config
cls
py configurar.py
pause
goto menu

:test_alert
cls
py test_alert.py
pause
goto menu
