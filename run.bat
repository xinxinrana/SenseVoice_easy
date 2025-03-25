@echo off
cd "D:\Code\Github\SenseVoice"
if not exist "%~dp0start_hidden.vbs" (
    echo CreateObject^("WScript.Shell"^).Run """" ^& WScript.Arguments^(0^) ^& """", 0, False > "%~dp0start_hidden.vbs"
)
wscript.exe "%~dp0start_hidden.vbs" "%~dp0hotkey_recorder.py"
