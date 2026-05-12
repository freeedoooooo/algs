namespace AdbMonitor.Gui;

internal static class MonitorPaths
{
    public static string ResolveFromBase(string baseDir, string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        return Path.IsPathRooted(value) ? value : Path.GetFullPath(Path.Combine(baseDir, value));
    }

    public static string FindMonitorRoot(string startDir)
    {
        var current = new DirectoryInfo(startDir);
        while (current != null)
        {
            if (File.Exists(Path.Combine(current.FullName, "monitor.config")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return startDir;
    }

    public static string LogBaseName(string fileName)
    {
        var name = Path.GetFileNameWithoutExtension(fileName);
        return string.IsNullOrWhiteSpace(name) ? "monitor" : name;
    }

    public static string LatestLogPath(string logDirectory, string logFileName)
    {
        if (string.IsNullOrWhiteSpace(logDirectory) || string.IsNullOrWhiteSpace(logFileName) || !Directory.Exists(logDirectory))
        {
            return string.Empty;
        }

        var baseName = LogBaseName(logFileName);
        var latest = new DirectoryInfo(logDirectory)
            .EnumerateFiles($"{baseName}-*.log")
            .OrderByDescending(x => x.LastWriteTimeUtc)
            .FirstOrDefault();

        return latest?.FullName ?? string.Empty;
    }
}
