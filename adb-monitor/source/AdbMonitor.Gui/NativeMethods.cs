using System.Runtime.InteropServices;

namespace AdbMonitor.Gui;

internal static class NativeMethods
{
    internal const int EmGetScrollPos = 0x04DD;
    internal const int EmSetScrollPos = 0x04DE;

    [StructLayout(LayoutKind.Sequential)]
    internal struct Point
    {
        public int X;
        public int Y;
    }

    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    internal static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, ref Point lParam);
}
