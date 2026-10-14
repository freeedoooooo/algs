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
  getMonth,
  remind
};
