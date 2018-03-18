@ECHO OFF
ECHO Working mode: %1
SET filename=%~dp0.env-%1.bat
ECHO Opening env file %filename%
CALL %filename%
ECHO Running upload.py
py upload.py
PAUSE