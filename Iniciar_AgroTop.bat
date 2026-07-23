@echo off
title AgroTop - Servidor
cd /d "%~dp0"
echo ============================================
echo   AgroTop - Iniciando o servidor...
echo   Nao feche esta janela enquanto usar o app.
echo ============================================
echo.
python -m streamlit run app.py
echo.
echo O servidor foi encerrado. Pressione uma tecla para fechar.
pause >nul
