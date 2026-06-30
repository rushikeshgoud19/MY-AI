Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the folder where this script is located (the workspace root)
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = currentDir

' 1. (REMOVED) The Python Backend now runs 24/7 on the Azure Cloud.

' 2. Start the Tauri Frontend App (or dev server)
tauriApp = currentDir & "\src-tauri\target\release\mizune-ai.exe"
' If the release exe doesn't exist, you can use npm run dev instead
WshShell.Run """" & tauriApp & """", 1, False

Set WshShell = Nothing
Set fso = Nothing
