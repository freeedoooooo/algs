// pages/cook/cook.js
const app = getApp();
const { createTimerManager, formatRemain } = require('../../utils/timer.js');
const { remind } = require('../../utils/format.js');
const { callFunction } = require('../../utils/request.js');

Page({
  data: {
    recipe: null,
    steps: [],          // 原始 timelineSteps 增强 _status / _remainText
    floatItems: [],     // 悬浮倒计时数据
    doneCount: 0,
    allDone: false,
    viewOnly: false     // 预览模式：只看步骤，不锁屏常亮
  },

  onLoad(query) {
    const viewOnly = !!(query && query.viewOnly);
    const recipe = app.globalData.currentRecipe;
    if (!recipe || !recipe.timelineSteps || !recipe.timelineSteps.length) {
      wx.showToast({ title: '缺少烹饪步骤', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1200);
      return;
    }

    this.timerMgr = createTimerManager();
    this.deducted = false; // 防止重复扣减库存

    const steps = recipe.timelineSteps.map(s =>
      Object.assign({}, s, { _status: 'pending', _remainText: '' })
    );
    this.setData({ recipe, steps, viewOnly });

    // 正式烹饪时保持屏幕常亮；预览模式不锁屏
    if (!viewOnly) {
      wx.setKeepScreenOn({ keepScreenOn: true, fail() {} });
    }
  },

  onUnload() {
    if (this.timerMgr) this.timerMgr.clearAll();
    wx.setKeepScreenOn({ keepScreenOn: false, fail() {} });
  },

  // 根据运行中的步骤重建悬浮倒计时数据
  refreshFloat() {
    const floatItems = this.data.steps
      .map((s, index) => ({ s, index }))
      .filter(({ s }) => s._status === 'running')
      .map(({ s, index }) => {
        const remain = this.timerMgr.getRemain('step_' + index);
        return {
          key: 'step_' + index,
          label: `${s.time} ${s.action.slice(0, 6)}`,
          remainText: formatRemain(remain),
          urgent: remain <= 10
        };
      });
    this.setData({ floatItems });
  },

  // 开始某个节点的倒计时
  onStartTimer(e) {
    if (this.data.viewOnly) return; // 预览模式禁用倒计时
    const index = e.detail.index;
    const step = this.data.steps[index];
    if (!step || !step.timer) return;

    const key = 'step_' + index;
    const seconds = step.timer * 60;

    this.setData({ [`steps[${index}]._status`]: 'running', [`steps[${index}]._remainText`]: formatRemain(seconds) });

    this.timerMgr.start(key, seconds, {
      onTick: (remain) => {
        this.setData({ [`steps[${index}]._remainText`]: formatRemain(remain) });
        this.refreshFloat();
      },
      onFinish: () => {
        // 到点提醒：预览模式仅文字提示，不震动/不响铃
        if (this.data.viewOnly) {
          wx.showToast({ title: `「${step.action}」时间到！（预览）`, icon: 'none' });
        } else {
          remind(`「${step.action}」时间到！`);
        }
        this.markDone(index);
      }
    });

    this.refreshFloat();
  },

  // 手动标记完成
  onStepDone(e) {
    if (this.data.viewOnly) return; // 预览模式禁用完成
    this.markDone(e.detail.index);
  },

  markDone(index) {
    const key = 'step_' + index;
    this.timerMgr.stop(key);
    this.setData({ [`steps[${index}]._status`]: 'done', [`steps[${index}]._remainText`]: '' });

    const doneCount = this.data.steps.filter(s => s._status === 'done').length;
    const allDone = doneCount >= this.data.steps.length;
    this.setData({ doneCount, allDone });
    this.refreshFloat();

    if (allDone) {
      wx.showToast({ title: '🎉 全部完成，开饭！', icon: 'none', duration: 2500 });
      this.deductInventory();
    }
  },

  // 一键全部完成
  onAllDone() {
    if (this.timerMgr) this.timerMgr.clearAll();
    const steps = this.data.steps.map(s => Object.assign({}, s, { _status: 'done', _remainText: '' }));
    this.setData({ steps, doneCount: steps.length, allDone: true, floatItems: [] });
    wx.showToast({ title: '🎉 全部完成，开饭！', icon: 'none', duration: 2500 });
    this.deductInventory();
  },

  // 完成烹饪后按菜谱 BOM 自动扣减库存（静默、仅一次）
  deductInventory() {
    if (this.deducted) return;
    if (this.data.viewOnly) return; // 预览模式不扣减库存，避免误触发
    const recipe = this.data.recipe;
    if (!recipe || !recipe._id) return;
    this.deducted = true;
    callFunction('inventory', { action: 'deduct', recipeId: recipe._id }, { loading: false, showError: false })
      .then(res => {
        const n = (res && res.deducted && res.deducted.length) || 0;
        if (n > 0) {
          setTimeout(() => {
            wx.showToast({ title: `已扣减 ${n} 种库存食材`, icon: 'none', duration: 2000 });
          }, 1200);
        }
      })
      .catch(() => { this.deducted = false; });
  },

  // 点击悬浮倒计时，滚动定位（此处简单提示）
  onTapFloat(e) {
    const remain = this.timerMgr.getRemain(e.detail.key);
    wx.showToast({ title: `剩余 ${formatRemain(remain)}`, icon: 'none' });
  },

  onBack() {
    wx.navigateBack();
  }
});
