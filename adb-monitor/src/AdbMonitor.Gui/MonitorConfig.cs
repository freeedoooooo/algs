using System.Globalization;

namespace AdbMonitor.Gui;

internal sealed class MonitorConfig
{
    private readonly Dictionary<string, string> _values = new(StringComparer.OrdinalIgnoreCase);

    public static MonitorConfig Load(string path)
    {
        if (!File.Exists(path))
        {
            throw new FileNotFoundException($"配置文件不存在：{path}", path);
        }

        var config = new MonitorConfig();
        foreach (var rawLine in File.ReadAllLines(path, System.Text.Encoding.UTF8))
        {
            var line = rawLine.Trim();
            if (line.Length == 0 || line.StartsWith('#') || line.StartsWith(';'))
            {
                continue;
            }

            var index = line.IndexOf('=');
            if (index <= 0)
            {
                continue;
            }

            var key = line[..index].Trim();
            var value = line[(index + 1)..].Trim();
            config._values[key] = value;
        }

        return config;
    }

    public string GetString(string key, string defaultValue = "")
        => _values.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value) ? value : defaultValue;

    public int GetInt(string key, int defaultValue)
        => int.TryParse(GetString(key), NumberStyles.Integer, CultureInfo.InvariantCulture, out var value) ? value : defaultValue;

    public bool GetBool(string key, bool defaultValue)
        => bool.TryParse(GetString(key), out var value) ? value : defaultValue;
}
