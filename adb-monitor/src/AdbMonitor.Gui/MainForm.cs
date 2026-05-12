using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Windows.Forms;

namespace AdbMonitor.Gui;

internal sealed class MainForm : Form
{
    private readonly string _appRoot;
    private readonly string _configPath;
    private readonly string _runnerScriptPath;
    private readonly RichTextBox _logBox = new();
    private readonly Label _stateLabel = new();
    private readonly Label _cooldownLabel = new();
    private readonly ToolStripStatusLabel _statusLabel = new();
    private readonly Timer _timer = new();
    private int _backendPid;

    public MainForm()
    {
        _appRoot = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        _configPath = Path.Combine(_appRoot, "monitor.config");
        _runnerScriptPath = Path.Combine(_appRoot, "core", "runner.ps1");

        Text = "模拟器监控";
        StartPosition = FormStartPosition.CenterScreen;
        Width = 1400;
        Height = 900;
        MinimumSize = new Size(1200, 760);
        Font = new Font("Microsoft YaHei UI", 10);

        var topPanel = BuildTopPanel();
        var statusStrip = BuildStatusStrip();

        _logBox.Dock = DockStyle.Fill;
        _logBox.ReadOnly = true;
        _logBox.Font = new Font("Consolas", 10);
        _logBox.BackColor = Color.White;
        _logBox.BorderStyle = BorderStyle.FixedSingle;

        Controls.Add(_logBox);
        Controls.Add(topPanel);
        Controls.Add(statusStrip);

        _timer.Interval = 3000;
        _timer.Tick += (_, _) => RefreshView();

        Shown += (_, _) =>
        {
            try
            {
                StartBackend();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"启动失败：{ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }

            RefreshView();
            _timer.Start();
        };

        FormClosing += (_, _) => StopBackend();
    }

    private Control BuildTopPanel()
    {
        var panel = new Panel
        {
            Dock = DockStyle.Top,
            Height = 92,
            Padding = new Padding(10),
        };

        var startBtn = MakeButton("启动监控", 10);
        var stopBtn = MakeButton("停止监控", 110);
        var refreshBtn = MakeButton("刷新日志", 210);
        var openConfigBtn = MakeButton("打开配置", 310);
        var clearCooldownBtn = MakeButton("清空冷却", 410);

        startBtn.Click += (_, _) =>
        {
            try
            {
                var pid = StartBackend();
                _statusLabel.Text = $"已启动监控，PID={pid}";
                RefreshView();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"启动失败：{ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        };

        stopBtn.Click += (_, _) =>
        {
            try
            {
                StopBackend();
                _statusLabel.Text = "已停止监控";
                RefreshView();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"停止失败：{ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        };

        refreshBtn.Click += (_, _) => RefreshView();
        openConfigBtn.Click += (_, _) => Process.Start(new ProcessStartInfo(_configPath) { UseShellExecute = true });
        clearCooldownBtn.Click += (_, _) =>
        {
            try
            {
                ClearCooldownState();
                _statusLabel.Text = "邮件冷却已清空";
                RefreshView();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"清空失败：{ex.Message}", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        };

        _stateLabel.AutoSize = true;
        _stateLabel.Left = 10;
        _stateLabel.Top = 55;
        _stateLabel.Text = "状态：未知";

        _cooldownLabel.AutoSize = true;
        _cooldownLabel.Left = 360;
        _cooldownLabel.Top = 55;
        _cooldownLabel.Text = "邮件冷却：未知";

        panel.Controls.AddRange(new Control[] { startBtn, stopBtn, refreshBtn, openConfigBtn, clearCooldownBtn, _stateLabel, _cooldownLabel });
        return panel;
    }

    private StatusStrip BuildStatusStrip()
    {
        var strip = new StatusStrip();
        _statusLabel.Text = "就绪";
        strip.Items.Add(_statusLabel);
        return strip;
    }

    private static Button MakeButton(string text, int left)
        => new()
        {
            Text = text,
            Width = 92,
            Left = left,
            Top = 12,
        };

    private MonitorConfig LoadConfig() => MonitorConfig.Load(_configPath);

    private string ConfigDir => Path.GetDirectoryName(_configPath) ?? _appRoot;

    private string RunnerPidPath()
    {
        var config = LoadConfig();
        var value = config.GetString("runner_pid_file", @".\runtime\runner.pid");
        return MonitorPaths.ResolveFromBase(ConfigDir, value);
    }

    private string AlertStatePath()
    {
        var config = LoadConfig();
        var value = config.GetString("alert_state_file", @".\runtime\alert.state.json");
        return MonitorPaths.ResolveFromBase(ConfigDir, value);
    }

    private string LogDirectory()
    {
        var config = LoadConfig();
        var value = config.GetString("log_directory", @".\log");
        return MonitorPaths.ResolveFromBase(ConfigDir, value);
    }

    private string LogFileName()
    {
        var config = LoadConfig();
        return config.GetString("log_file_name", "monitor.log");
    }

    private int CooldownMinutes()
    {
        var config = LoadConfig();
        return config.GetInt("alert_cooldown_minutes", 30);
    }

    private void RefreshView()
    {
        var latestLog = MonitorPaths.LatestLogPath(LogDirectory(), LogFileName());
        var lines = string.IsNullOrWhiteSpace(latestLog) ? Array.Empty<string>() : ReadTail(latestLog, 500);
        RenderLogLines(lines);
        UpdateStateLabel();
        UpdateCooldownLabel();
        _statusLabel.Text = $"最后刷新：{DateTime.Now:HH:mm:ss}";
    }

    private static string[] ReadTail(string path, int tailLines)
    {
        try
        {
            return File.ReadLines(path).TakeLast(tailLines).ToArray();
        }
        catch (Exception ex)
        {
            return new[] { $"读取日志失败：{ex.Message}" };
        }
    }

    private void RenderLogLines(string[] lines)
    {
        var atBottom = IsAtBottom();
        var scrollPos = GetScrollPos();

        _logBox.SuspendLayout();
        _logBox.Clear();

        if (lines.Length == 0)
        {
            AppendColoredLine("暂无日志。", Color.Gray);
        }
        else
        {
            foreach (var line in lines)
            {
                AppendColoredLine(line, GetLogLineColor(line));
            }
        }

        if (atBottom)
        {
            _logBox.SelectionStart = _logBox.TextLength;
            _logBox.ScrollToCaret();
        }
        else
        {
            SetScrollPos(scrollPos);
        }

        _logBox.ResumeLayout();
    }

    private void AppendColoredLine(string line, Color color)
    {
        _logBox.SelectionStart = _logBox.TextLength;
        _logBox.SelectionLength = 0;
        _logBox.SelectionColor = color;
        _logBox.AppendText(line + Environment.NewLine);
    }

    private static Color GetLogLineColor(string line)
        => line.Contains("[ERROR]", StringComparison.OrdinalIgnoreCase) ? Color.Firebrick
         : line.Contains("[WARN]", StringComparison.OrdinalIgnoreCase) ? Color.DarkOrange
         : line.Contains("[STEP]", StringComparison.OrdinalIgnoreCase) ? Color.Teal
         : line.Contains("[INFO]", StringComparison.OrdinalIgnoreCase) ? Color.DimGray
         : Color.Black;

    private bool IsAtBottom()
    {
        if (_logBox.TextLength == 0)
        {
            return true;
        }

        var point = new Point(1, Math.Max(_logBox.ClientSize.Height - 2, 1));
        var idx = _logBox.GetCharIndexFromPosition(point);
        return idx >= _logBox.TextLength - 80;
    }

    private NativeMethods.Point GetScrollPos()
    {
        var point = new NativeMethods.Point();
        _ = NativeMethods.SendMessage(_logBox.Handle, NativeMethods.EmGetScrollPos, IntPtr.Zero, ref point);
        return point;
    }

    private void SetScrollPos(NativeMethods.Point point)
        => _ = NativeMethods.SendMessage(_logBox.Handle, NativeMethods.EmSetScrollPos, IntPtr.Zero, ref point);

    private void UpdateStateLabel()
    {
        if (_backendPid > 0 && ProcessExists(_backendPid))
        {
            _stateLabel.Text = $"状态：运行中，PID={_backendPid}";
            _stateLabel.ForeColor = Color.ForestGreen;
            return;
        }

        var pidText = File.Exists(RunnerPidPath()) ? File.ReadAllText(RunnerPidPath()).Trim() : string.Empty;
        if (int.TryParse(pidText, out var pid) && ProcessExists(pid))
        {
            _backendPid = pid;
            _stateLabel.Text = $"状态：运行中，PID={pid}";
            _stateLabel.ForeColor = Color.ForestGreen;
            return;
        }

        _backendPid = 0;
        _stateLabel.Text = "状态：未运行";
        _stateLabel.ForeColor = Color.Crimson;
    }

    private static bool ProcessExists(int pid)
    {
        try
        {
            using var process = Process.GetProcessById(pid);
            return !process.HasExited;
        }
        catch
        {
            return false;
        }
    }

    private void UpdateCooldownLabel()
    {
        var path = AlertStatePath();
        var cooldownMinutes = CooldownMinutes();

        if (cooldownMinutes <= 0)
        {
            _cooldownLabel.Text = "邮件冷却：未启用";
            _cooldownLabel.ForeColor = Color.ForestGreen;
            return;
        }

        if (!File.Exists(path))
        {
            _cooldownLabel.Text = "邮件冷却：无";
            _cooldownLabel.ForeColor = Color.ForestGreen;
            return;
        }

        try
        {
            var json = File.ReadAllText(path);
            var state = JsonSerializer.Deserialize<AlertState>(json);
            if (string.IsNullOrWhiteSpace(state?.LastAlertAt))
            {
                _cooldownLabel.Text = "邮件冷却：无";
                _cooldownLabel.ForeColor = Color.ForestGreen;
                return;
            }

            var lastAlertAt = DateTime.Parse(state.LastAlertAt, null, System.Globalization.DateTimeStyles.RoundtripKind);
            var remaining = TimeSpan.FromMinutes(cooldownMinutes) - (DateTime.Now - lastAlertAt);
            if (remaining <= TimeSpan.Zero)
            {
                _cooldownLabel.Text = "邮件冷却：已结束";
                _cooldownLabel.ForeColor = Color.ForestGreen;
                return;
            }

            _cooldownLabel.Text = $"邮件冷却：剩余 {FormatDuration(remaining)}";
            _cooldownLabel.ForeColor = Color.DarkOrange;
        }
        catch
        {
            _cooldownLabel.Text = "邮件冷却：状态异常";
            _cooldownLabel.ForeColor = Color.DarkOrange;
        }
    }

    private static string FormatDuration(TimeSpan duration)
    {
        var totalSeconds = Math.Max((int)Math.Ceiling(duration.TotalSeconds), 0);
        var hours = totalSeconds / 3600;
        var minutes = (totalSeconds % 3600) / 60;
        var seconds = totalSeconds % 60;
        return hours > 0 ? $"{hours:D2}:{minutes:D2}:{seconds:D2}" : $"{minutes:D2}:{seconds:D2}";
    }

    private void ClearCooldownState()
    {
        var path = AlertStatePath();
        if (File.Exists(path))
        {
            File.Delete(path);
        }
    }

    private int StartBackend()
    {
        var existing = GetRunningBackendPid();
        if (existing > 0)
        {
            _backendPid = existing;
            return existing;
        }

        var psi = new ProcessStartInfo
        {
            FileName = "powershell.exe",
            Arguments = $"-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"{_runnerScriptPath}\" -ConfigPath \"{_configPath}\"",
            WorkingDirectory = _appRoot,
            UseShellExecute = false,
            CreateNoWindow = true,
        };

        var proc = Process.Start(psi) ?? throw new InvalidOperationException("无法启动监控后台。");
        _backendPid = proc.Id;
        return proc.Id;
    }

    private int GetRunningBackendPid()
    {
        var pidPath = RunnerPidPath();
        if (!File.Exists(pidPath))
        {
            return 0;
        }

        var pidText = File.ReadAllText(pidPath).Trim();
        if (int.TryParse(pidText, out var pid) && ProcessExists(pid))
        {
            return pid;
        }

        try
        {
            File.Delete(pidPath);
        }
        catch
        {
        }

        return 0;
    }

    private void StopBackend()
    {
        if (_backendPid > 0)
        {
            TryKill(_backendPid);
            _backendPid = 0;
        }

        var pidPath = RunnerPidPath();
        if (!File.Exists(pidPath))
        {
            return;
        }

        if (int.TryParse(File.ReadAllText(pidPath).Trim(), out var pid))
        {
            TryKill(pid);
        }

        try
        {
            File.Delete(pidPath);
        }
        catch
        {
        }
    }

    private static void TryKill(int pid)
    {
        try
        {
            using var process = Process.GetProcessById(pid);
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch
        {
        }
    }

    private sealed class AlertState
    {
        public string? LastAlertAt { get; set; }
    }
}
