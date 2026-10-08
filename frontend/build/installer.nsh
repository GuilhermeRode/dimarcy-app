; Picked up automatically by electron-builder (build/installer.nsh).
;
; electron-builder 26 decides "the app is running" when ANY process runs from the install folder
; (PowerShell path-prefix check). On an upgrade the previous version's uninstaller runs from that
; folder, so the installer mistook it for the app and stopped with "não é possível fechar o
; Di Marcy Pedidos". This replaces that check: only the app's own executable, by exact name and
; for the current user, counts as "running".
!macro customCheckAppRunning
  nsExec::Exec `"$SYSDIR\cmd.exe" /C tasklist /FI "USERNAME eq %USERNAME%" /FI "IMAGENAME eq ${APP_EXECUTABLE_FILENAME}" /FO CSV /NH | "$SYSDIR\findstr.exe" /B /I /C:"\"${APP_EXECUTABLE_FILENAME}\""`
  Pop $R0
  ${if} $R0 == 0
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "$(appRunning)" /SD IDOK IDOK +2
    Quit
    DetailPrint "$(appClosing)"
    nsExec::Exec `"$SYSDIR\cmd.exe" /C taskkill /F /IM "${APP_EXECUTABLE_FILENAME}" /FI "USERNAME eq %USERNAME%"`
    Pop $R0
    Sleep 1500 ; let Windows release the files
  ${endIf}
!macroend
