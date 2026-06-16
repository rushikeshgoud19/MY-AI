Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "taskkill /f /im pythonw.exe", 0, True
WshShell.Run "pythonw.exe mizune.py", 1
Set WshShell = Nothing
