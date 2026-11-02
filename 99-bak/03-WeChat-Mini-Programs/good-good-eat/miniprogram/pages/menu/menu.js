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
    swapping: false,
    favSet: {}
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

    const ctx = app.globalData.recommendCtx || {};
    callFunction('recommendMenu', {
      scene: this.data.scene,
      month: getMonth(),
      preferences: (app.globalData.userInfo && app.globalData.userInfo.preferences) || {},
      preferInventory: !!ctx.preferInventory,
      inventory: ctx.inventory || []
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

  onShow() {
    this.loadFavorites();
  },

  // 拉取收藏状态，标记每道菜是否已收藏
  loadFavorites() {
    callFunction('favorites', { action: 'list' }, { loading: false, showError: false })
      .then(res => {
        const favSet = {};
        ((res && res.favorites) || []).forEach(f => { favSet[f.recipeId] = true; });
        this.setData({ favSet });
      })
      .catch(() => {});
  },

  // 收藏 / 取消收藏单道菜（乐观更新，失败回滚）
  onToggleFavorite(e) {
    const { recipe, favorited } = e.detail;
    if (!recipe || !recipe._id) return;
    const recipeId = recipe._id;
    const payload = favorited
      ? { action: 'add', recipe }
      : { action: 'remove', recipeId };

    const favSet = Object.assign({}, this.data.favSet);
    if (favorited) favSet[recipeId] = true; else delete favSet[recipeId];
    this.setData({ favSet });

    callFunction('favorites', payload, { loading: false, showError: false })
      .then(() => {
        wx.showToast({ title: favorited ? '已收藏' : '已取消收藏', icon: 'none' });
      })
      .catch(() => {
        const back = Object.assign({}, this.data.favSet);
        if (favorited) delete back[recipeId]; else back[recipeId] = true;
        this.setData({ favSet: back });
      });
  },

  onBack() {
    wx.navigateBack();
  }
});
