Option Explicit
Dim shell, projectDir, batPath
Set shell = CreateObject("WScript.Shell")
projectDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
batPath = projectDir & "\START_OZON_MANAGER.bat"
shell.Run """" & batPath & """", 1, False
Set shell = Nothing
