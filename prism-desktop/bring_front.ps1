Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object { $_.MainWindowHandle } | Where-Object { $_ -ne 0 } | ForEach-Object { [Win32]::ShowWindow($_, 9); [Win32]::SetForegroundWindow($_); Write-Host "brought to front" }
