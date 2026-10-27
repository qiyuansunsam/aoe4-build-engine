# Disabled (Sam, 2026-10-27): recordings run full screen at the player's own display settings, so there is no window
# to tuck. The windowed variant (SetWindowPos to the bottom-right corner, HWND_BOTTOM, no activation) is kept in git
# history of this file for a windowmode-2 run.
param([string]$Process = "RelicCardinal", [int]$Width = 960, [int]$Height = 540)
Write-Output "tuck disabled: full-screen recording"
