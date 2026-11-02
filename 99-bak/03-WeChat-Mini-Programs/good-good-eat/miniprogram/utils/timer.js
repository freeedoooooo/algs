// utils/timer.js
// 多路倒计时管理器：支持同时运行多个独立倒计时（用于多线程烹饪导航）

/**
 * 创建一个倒计时管理器
 * 用法：
 *   const mgr = createTimerManager();
 *   mgr.start('step_1', 120, { onTick: (remain)=>{}, onFinish: ()=>{} });
 *   mgr.pause('step_1'); mgr.resume('step_1'); mgr.stop('step_1');
 *   mgr.clearAll(); // 页面卸载时调用
 */
function createTimerManager() {
  const timers = {}; // key -> { remain, intervalId, onTick, onFinish, running }

  function start(key, seconds, callbacks = {}) {
    stop(key); // 避免重复
    const { onTick, onFinish } = callbacks;
    const timer = {
      remain: seconds,
      running: true,
      onTick,
      onFinish,
      intervalId: null
    };
    timer.intervalId = setInterval(() => {
      if (!timer.running) return;
      timer.remain -= 1;
      if (typeof onTick === 'function') {
        onTick(timer.remain, key);
      }
      if (timer.remain <= 0) {
        clearInterval(timer.intervalId);
        timer.running = false;
        if (typeof onFinish === 'function') {
          onFinish(key);
        }
      }
    }, 1000);
    timers[key] = timer;
    if (typeof onTick === 'function') {
      onTick(timer.remain, key); // 立即回调一次初始值
    }
    return key;
  }

  function pause(key) {
    const t = timers[key];
    if (t) t.running = false;
  }

  function resume(key) {
    const t = timers[key];
    if (t && t.remain > 0) t.running = true;
  }

  function stop(key) {
    const t = timers[key];
    if (t) {
      clearInterval(t.intervalId);
      delete timers[key];
    }
  }

  function getRemain(key) {
    return timers[key] ? timers[key].remain : 0;
  }

  function clearAll() {
    Object.keys(timers).forEach(k => stop(k));
  }

  return { start, pause, resume, stop, getRemain, clearAll };
}

/**
 * 将秒数格式化为 mm:ss
 */
function formatRemain(sec) {
  const s = Math.max(0, Math.floor(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
}

module.exports = {
  createTimerManager,
  formatRemain
};
