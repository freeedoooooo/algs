// utils/format.js
// 通用格式化与提醒辅助

// 场景筛选器配置（与云函数 scene 入参保持一致）
const SCENES = [
  { key: 'quick', label: '⚡ 快手菜', desc: '15分钟内搞定' },
  { key: 'easy', label: '🍳 简单菜', desc: '零失败新手友好' },
  { key: 'feast', label: '🍲 周末大菜', desc: '硬菜露一手' }
];

// 菜谱类型标签
const TYPE_LABEL = {
  meat: '荤',
  vegetable: '素',
  soup: '汤',
  staple: '主食'
};

// 步骤类型样式
const STEP_TYPE_LABEL = {
  prep: '备',
  cook: '烹',
  wait: '等'
};

// 库存食材分类
const ING_CATEGORIES = [
  { key: 'vegetable', label: '🥬 蔬菜' },
  { key: 'meat', label: '🍖 肉蛋' },
  { key: 'seafood', label: '🦐 水产' },
  { key: 'fruit', label: '🍎 水果' },
  { key: 'other', label: '🧺 其他' }
];

const CATEGORY_LABEL = ING_CATEGORIES.reduce((m, c) => {
  m[c.key] = c.label;
  return m;
}, {});

// 库存状态展示元数据
const STATUS_META = {
  expired: { label: '已过期', color: '#E53935' },
  expiring: { label: '临期', color: '#FB8C00' },
  normal: { label: '新鲜', color: '#43A047' }
};

const EXPIRING_DAYS = 2; // 临期阈值，与云函数保持一致

function pad(n) {
  return n < 10 ? '0' + n : '' + n;
}

// 今天日期字符串 YYYY-MM-DD
function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// 距今 n 天后的日期字符串（n 可为负）
function dateAfter(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// 距过期天数：正=还剩几天，负=已过期几天，null=无保质期
function daysUntil(dateStr) {
  if (!dateStr) return null;
  const t = new Date(todayStr() + 'T00:00:00').getTime();
  const e = new Date(dateStr + 'T00:00:00').getTime();
  if (isNaN(e)) return null;
  return Math.round((e - t) / 86400000);
}

// 根据保质期计算状态
function ingStatus(dateStr) {
  const d = daysUntil(dateStr);
  if (d === null) return 'normal';
  if (d < 0) return 'expired';
  if (d <= EXPIRING_DAYS) return 'expiring';
  return 'normal';
}

/**
 * 在库存列表中按名称模糊匹配（text 包含食材名即命中）
 * @param {string} text 待匹配文本（如备菜项 "番茄 2个"）
 * @param {Array<{name:string, expiring?:boolean}>} stockList 可用库存（已排除过期）
 * @returns {{name:string, expiring:boolean}|null}
 */
function matchStock(text, stockList) {
  if (!text || !Array.isArray(stockList)) return null;
  return stockList.find(s => s && s.name && text.indexOf(s.name) >= 0) || null;
}

/**
 * 获取当前月份 (1-12)
 */
function getMonth() {
  return new Date().getMonth() + 1;
}

/**
 * 到点提醒：震动 + 提示音
 * @param {string} text 展示文案（可选）
 */
function remind(text) {
  wx.vibrateLong({ fail() {} });
  if (text) {
    wx.showToast({ title: text, icon: 'none', duration: 2500 });
  }
  // 播放提示音（若存在 /assets/notify.mp3）
  try {
    const audio = wx.createInnerAudioContext();
    audio.src = '/assets/notify.mp3';
    audio.play();
    audio.onEnded(() => audio.destroy());
    audio.onError(() => audio.destroy());
  } catch (e) {
    // 忽略音频错误
  }
}

module.exports = {
  SCENES,
  TYPE_LABEL,
  STEP_TYPE_LABEL,
  ING_CATEGORIES,
  CATEGORY_LABEL,
  STATUS_META,
  EXPIRING_DAYS,
  getMonth,
  todayStr,
  dateAfter,
  daysUntil,
  ingStatus,
  matchStock,
  remind
};
