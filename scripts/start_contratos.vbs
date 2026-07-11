Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

projectRoot = objShell.CurrentDirectory
batScript = projectRoot & "\scripts\start_system.bat"

If Not objFSO.FileExists(batScript) Then
    MsgBox "ERRO: script nao encontrado em " & batScript, vbCritical, "Sistema de Contratos"
    WScript.Quit 1
End If

objShell.Run batScript, 0, False

WScript.Sleep 3000
objShell.Run "http://127.0.0.1:8000/login", 1, False

WScript.Quit 0
