// pages/favorites/favorites.js
const { callFunction } = require('../../utils/request.js');
const { TYPE_LABEL } = require('../../utils/format.js');

Page({
  data: {
    loading: true,
    list: []
  },

  onShow() {
    this.loadList();
  },

  loadList() {
    this.setData({ loading: true });
    callFunction('favorites', { action: 'list' }, { loading: false, showError: false })
      .then(res => {
        const favorites = (res && res.favorites) || [];
        const list = favorites.map(f => Object.assign({}, f, {
          typeText: TYPE_LABEL[f.type] || '菜',
          timeText: f.estimatedTime ? f.estimatedTime + ' 分钟' : ''
        }));
        this.setData({ list, loading: false });
      })
      .catch(() => this.setData({ loading: false }));
  },

  // 点击某道菜 → 进入备菜清单，直接开做这一道菜
  onOpen(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: '/pages/prep/prep?id=' + id });
  },

  // 取消收藏
  onRemove(e) {
    const id = e.currentTarget.dataset.id;
    const name = e.currentTarget.dataset.name || '这道菜';
    wx.showModal({
      title: '取消收藏',
      content: `把「${name}」从收藏中移除？`,
      confirmColor: '#E53935',
      success: (res) => {
        if (!res.confirm) return;
        callFunction('favorites', { action: 'remove', recipeId: id }, { loadingText: '移除中...' })
          .then(() => this.loadList())
          .catch(() => {});
      }
    });
  }
});
