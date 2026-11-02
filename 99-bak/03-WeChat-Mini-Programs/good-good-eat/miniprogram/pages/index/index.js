// pages/index/index.js
const app = getApp();
const { callFunction } = require('../../utils/request.js');
const { SCENES, getMonth } = require('../../utils/format.js');

Page({
  data: {
    scenes: SCENES,
    activeScene: 'easy',
    activeDesc: SCENES[1].desc,
    loading: false,
    preferInventory: false,
    invSummary: { total: 0, expiring: 0, expired: 0 }
  },

  onShow() {
    this.loadInventorySummary();
  },

  // 静默拉取库存概览（首页角标 + 清库存推荐使用）
  loadInventorySummary() {
    callFunction('inventory', { action: 'list' }, { loading: false, showError: false })
      .then(res => {
        const items = (res && res.items) || [];
        // 过期食材不计入可用库存
        this._inventory = items
          .filter(i => i._status !== 'expired')
          .map(i => ({ name: i.name, expiring: i._status === 'expiring' }));
        this.setData({ invSummary: (res && res.summary) || { total: 0, expiring: 0, expired: 0 } });
      })
      .catch(() => {});
  },

  onSceneTap(e) {
    const { key, desc } = e.currentTarget.dataset;
    this.setData({ activeScene: key, activeDesc: desc });
  },

  onTogglePrefer(e) {
    this.setData({ preferInventory: e.detail.value });
  },

  onGoInventory() {
    wx.navigateTo({ url: '/pages/inventory/inventory' });
  },

  onGoFavorites() {
    wx.navigateTo({ url: '/pages/favorites/favorites' });
  },

  onRecommend() {
    if (this.data.loading) return;
    this.setData({ loading: true });

    const preferInventory = this.data.preferInventory;
    const inventory = this._inventory || [];
    // 保存推荐上下文，供菜单页「换一换」沿用（保证标注一致）
    app.globalData.recommendCtx = {
      scene: this.data.activeScene,
      preferInventory,
      inventory
    };
    callFunction('recommendMenu', {
      scene: this.data.activeScene,
      month: getMonth(),
      preferences: (app.globalData.userInfo && app.globalData.userInfo.preferences) || {},
      preferInventory,
      inventory
    }, { loadingText: 'AI 正在配菜...' })
      .then(res => {
        if (!res || !res.menu || !res.menu.length) {
          wx.showToast({ title: '暂无推荐，请先初始化菜谱库', icon: 'none' });
          return;
        }
        // 通过 globalData 传递给菜单确认页
        app.globalData.currentMenu = {
          scene: this.data.activeScene,
          reason: res.reason,
          source: res.source,
          items: res.menu
        };
        wx.navigateTo({ url: '/pages/menu/menu' });
      })
      .catch(() => {})
      .finally(() => {
        this.setData({ loading: false });
      });
  }
});
