Start-Sleep -Seconds 10
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "telnet reflectionwall.local 23"
