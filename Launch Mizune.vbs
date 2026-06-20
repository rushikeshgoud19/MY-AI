Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the folder where this script is located (the workspace root)
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = currentDir

' 1. Start the Tauri Frontend App
tauriApp = currentDir & "\src-tauri\target\release\mizune-ai.exe"
WshShell.Run """" & tauriApp & """", 1, False



Set WshShell = Nothing
Set fso = Nothing
