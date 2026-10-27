# Mute (or unmute) the audio session of a running process by name, through the Windows Core Audio API.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File mute_game.ps1 [-Process RelicCardinal] [-Unmute]
param([string]$Process = "RelicCardinal", [switch]$Unmute)
$code = @"
using System;
using System.Runtime.InteropServices;
namespace Snd {
  [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumerator {}
  enum EDataFlow { eRender, eCapture, eAll }
  enum ERole { eConsole, eMultimedia, eCommunications }
  [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IMMDeviceEnumerator {
    int EnumAudioEndpoints(EDataFlow dataFlow, int dwStateMask, out IntPtr ppDevices);
    int GetDefaultAudioEndpoint(EDataFlow dataFlow, ERole role, out IMMDevice ppEndpoint);
  }
  [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IMMDevice {
    int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
  }
  [Guid("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IAudioSessionManager2 {
    int GetAudioSessionControl(IntPtr sessionGuid, int streamFlags, out IntPtr sessionControl);
    int GetSimpleAudioVolume(IntPtr sessionGuid, int streamFlags, out IntPtr audioVolume);
    int GetSessionEnumerator(out IAudioSessionEnumerator sessionEnum);
  }
  [Guid("E2F5BB11-0570-40CA-ACDD-3AA01277DEE8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IAudioSessionEnumerator {
    int GetCount(out int count);
    int GetSession(int index, out IAudioSessionControl2 session);
  }
  [Guid("BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IAudioSessionControl2 {
    int GetState(out int state);
    int GetDisplayName([MarshalAs(UnmanagedType.LPWStr)] out string name);
    int SetDisplayName([MarshalAs(UnmanagedType.LPWStr)] string value, IntPtr eventContext);
    int GetIconPath([MarshalAs(UnmanagedType.LPWStr)] out string path);
    int SetIconPath([MarshalAs(UnmanagedType.LPWStr)] string value, IntPtr eventContext);
    int GetGroupingParam(out Guid param);
    int SetGroupingParam(ref Guid param, IntPtr eventContext);
    int RegisterAudioSessionNotification(IntPtr client);
    int UnregisterAudioSessionNotification(IntPtr client);
    int GetSessionIdentifier([MarshalAs(UnmanagedType.LPWStr)] out string id);
    int GetSessionInstanceIdentifier([MarshalAs(UnmanagedType.LPWStr)] out string id);
    int GetProcessId(out uint pid);
    int IsSystemSoundsSession();
    int SetDuckingPreference(bool optOut);
  }
  [Guid("87CE5498-68D6-44E5-9215-6DA47EF883D8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface ISimpleAudioVolume {
    int SetMasterVolume(float level, IntPtr eventContext);
    int GetMasterVolume(out float level);
    int SetMute(bool mute, IntPtr eventContext);
    int GetMute(out bool mute);
  }
  public static class Mixer {
    public static int SetMute(uint[] pids, bool mute) {
      var enumerator = (IMMDeviceEnumerator)new MMDeviceEnumerator();
      IMMDevice device; enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender, ERole.eMultimedia, out device);
      var iid = typeof(IAudioSessionManager2).GUID; object o; device.Activate(ref iid, 23, IntPtr.Zero, out o);
      var manager = (IAudioSessionManager2)o; IAudioSessionEnumerator sessions; manager.GetSessionEnumerator(out sessions);
      int count; sessions.GetCount(out count); int done = 0;
      for (int i = 0; i < count; i++) {
        IAudioSessionControl2 s; sessions.GetSession(i, out s); uint pid; s.GetProcessId(out pid);
        if (Array.IndexOf(pids, pid) < 0) continue;
        ((ISimpleAudioVolume)s).SetMute(mute, IntPtr.Zero); done++;
      }
      return done;
    }
  }
}
"@
Add-Type -TypeDefinition $code
$pids = @(Get-Process -Name $Process -ErrorAction SilentlyContinue | ForEach-Object { [uint32]$_.Id })
if (-not $pids) { Write-Output "no $Process process"; exit 0 }
$n = [Snd.Mixer]::SetMute([uint32[]]$pids, -not $Unmute)
Write-Output "$(if ($Unmute) {'unmuted'} else {'muted'}) $n audio session(s) of $Process (pids $($pids -join ','))"
