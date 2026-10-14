// pages/index/index.js
const app = getApp();
const { callFunction } = require('../../utils/request.js');
const { SCENES, getMonth } = require('../../utils/format.js');

Page({
  data: {
    scenes: SCENES,
    activeScene: 'easy',
    activeDesc: SCENES[1].desc,
    loading: false
  },

  onSceneTap(e) {
    const { key, desc } = e.currentTarget.dataset;
    this.setData({ activeScene: key, activeDesc: desc });
  },

  onRecommend() {
    if (this.data.loading) return;
    this.setData({ loading: true });

    callFunction('recommendMenu', {
      scene: this.data.activeScene,
      month: getMonth(),
      preferences: (app.globalData.userInfo && app.globalData.userInfo.preferences) || {}
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
