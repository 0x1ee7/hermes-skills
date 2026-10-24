param([string]$Out, [string]$Steps = "", [string]$Exe = "D:\repo\target\debug\game.exe",
      [string]$Repo = "D:\repo")
# Starts the game, plays keys into ITS OWN window (PostMessage on its handle: no other window
# and no global input state is touched, unlike SendInput), and captures at each SHOT step.
# Steps, comma-separated:
#   KEYS:holdMs:waitMs   KEYS like "Q" or "S+D+SHIFT": all go down, wait holdMs, all go up
#   SHOT:name            PrintWindow capture to "$Out-name.png"
#   WAIT:ms              sleep
# Example: -Steps "SHOT:default,Q:80:400,Q:80:2500,SHOT:turned"
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public struct RECT { public int Left, Top, Right, Bottom; }
public static class W {
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
}
"@
# virtual key, scan code (set 1). winit derives the physical key from the scan code.
$keys = @{
  Q = @(0x51, 0x10); E = @(0x45, 0x12); W = @(0x57, 0x11); A = @(0x41, 0x1E)
  S = @(0x53, 0x1F); D = @(0x44, 0x20); TAB = @(0x09, 0x0F); SHIFT = @(0x10, 0x2A)
  SPACE = @(0x20, 0x39); ESC = @(0x1B, 0x01)
}
function Shot([IntPtr]$h, [string]$path) {
  $r = New-Object RECT; [W]::GetClientRect($h, [ref]$r) | Out-Null
  $bmp = New-Object System.Drawing.Bitmap $r.Right, $r.Bottom
  $g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
  [W]::PrintWindow($h, $hdc, 3) | Out-Null     # PW_CLIENTONLY | PW_RENDERFULLCONTENT
  $g.ReleaseHdc($hdc); $bmp.Save($path); $g.Dispose(); $bmp.Dispose()
  Write-Output "captured $path ($($r.Right)x$($r.Bottom))"
}
$env:ISO_EXIT_AFTER_FRAMES = "4000"   # safety exit
$proc = Start-Process -FilePath $Exe -WorkingDirectory $Repo -PassThru `
    -RedirectStandardError "$Out.log" -RedirectStandardOutput "$Out.out"
Start-Sleep -Seconds 4
$proc.Refresh(); $h = $proc.MainWindowHandle
foreach ($step in ($Steps -split ',')) {
  $p = $step.Trim() -split ':'
  if ($p[0] -eq 'SHOT') { Shot $h "$Out-$($p[1]).png"; continue }
  if ($p[0] -eq 'WAIT') { Start-Sleep -Milliseconds ([int]$p[1]); continue }
  $pressed = @($p[0] -split '\+' | ForEach-Object { $keys[$_.ToUpper()] })
  foreach ($k in $pressed) {   # WM_KEYDOWN, lParam: repeat 1, scan code in bits 16-23
    [W]::PostMessage($h, 0x100, [IntPtr]$k[0], [IntPtr]([int64]1 + ($k[1] * 65536))) | Out-Null
  }
  Start-Sleep -Milliseconds ([int]$p[1])
  foreach ($k in $pressed) {   # WM_KEYUP: bits 30 and 31 set (was down, is being released)
    $up = [int64]1 + ($k[1] * 65536) + 3221225472
    [W]::PostMessage($h, 0x101, [IntPtr]$k[0], [IntPtr]$up) | Out-Null
  }
  Start-Sleep -Milliseconds ([int]$p[2])
}
$proc.CloseMainWindow() | Out-Null
if (-not $proc.WaitForExit(8000)) { $proc.Kill() }
