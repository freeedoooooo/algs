// pages/menu/menu.js
const app = getApp();
const { callFunction } = require('../../utils/request.js');
const { getMonth } = require('../../utils/format.js');

Page({
  data: {
    reason: '',
    source: 'ai',
    scene: 'easy',
    items: [],
    swapping: false
  },

  onLoad() {
    const menu = app.globalData.currentMenu;
    if (!menu || !menu.items || !menu.items.length) {
      wx.showToast({ title: '菜单数据丢失', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1200);
      return;
    }
    this.setData({
      reason: menu.reason || '',
      source: menu.source || 'ai',
      scene: menu.scene || 'easy',
      items: menu.items
    });
  },

  // 换一换：重新调用推荐
  onSwap() {
    if (this.data.swapping) return;
    this.setData({ swapping: true });

    callFunction('recommendMenu', {
      scene: this.data.scene,
      month: getMonth(),
      preferences: (app.globalData.userInfo && app.globalData.userInfo.preferences) || {}
    }, { loadingText: '换一套...' })
      .then(res => {
        if (res && res.menu && res.menu.length) {
          this.setData({
            items: res.menu,
            reason: res.reason || '',
            source: res.source || 'ai'
          });
          app.globalData.currentMenu = {
            scene: this.data.scene,
            reason: res.reason,
            source: res.source,
            items: res.menu
          };
        }
      })
      .catch(() => {})
      .finally(() => {
        this.setData({ swapping: false });
      });
  },

  // 选择某道菜进入备菜清单
  onPickDish(e) {
    const { recipe } = e.detail;
    if (!recipe || !recipe._id) return;
    wx.navigateTo({ url: `/pages/prep/prep?id=${recipe._id}` });
  },

  onBack() {
    wx.navigateBack();
  }
});
