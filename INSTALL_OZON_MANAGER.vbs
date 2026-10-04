Option Explicit

Dim shell, fso, projectDir, launcher, iconPath, desktop, shortcutPath, shortcut
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = projectDir & "\START_OZON_MANAGER.vbs"
iconPath = projectDir & "\assets\ozon_manager.ico"
desktop = shell.SpecialFolders("Desktop")
shortcutPath = desktop & "\Ozon Manager.lnk"

Set shortcut = shell.CreateShortcut(shortcutPath)
shortcut.TargetPath = launcher
shortcut.WorkingDirectory = projectDir
shortcut.IconLocation = iconPath & ",0"
shortcut.Description = "Запуск Ozon Manager"
shortcut.WindowStyle = 1
shortcut.Save

MsgBox "Ярлык «Ozon Manager» создан на рабочем столе." & vbCrLf & vbCrLf & _
       "При первом запуске START_OZON_MANAGER.bat установит только зависимости приложения." & vbCrLf & vbCrLf & _
       "Сейчас будет запущен установочный запуск приложения.", _
       vbInformation, "Ozon Manager"

Dim startBat
startBat = projectDir & "\START_OZON_MANAGER.bat"
shell.Run """" & startBat & """", 1, False

Set shortcut = Nothing
Set shell = Nothing
Set fso = Nothing
