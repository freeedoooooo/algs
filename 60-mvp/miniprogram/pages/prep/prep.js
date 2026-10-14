// pages/prep/prep.js
const app = getApp();
const { callFunction } = require('../../utils/request.js');
const { matchStock } = require('../../utils/format.js');

// 三类清单的配置：数据字段 -> 展示标题
const GROUP_DEFS = [
  { key: 'mainIngredients', title: '🥬 主料 / 配料' },
  { key: 'seasonings', title: '🧂 调料' },
  { key: 'tools', title: '🍳 工具' }
];

Page({
  data: {
    recipeId: '',
    recipe: null,
    groups: [],
    total: 0,
    checkedCount: 0,
    allChecked: false,
    haveCount: 0,
    buyCount: 0,
    favorited: false
  },

  onLoad(query) {
    const id = query && query.id;
    if (!id) {
      wx.showToast({ title: '缺少菜谱参数', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1200);
      return;
    }
    this.setData({ recipeId: id });
    this.loadRecipe(id);
  },

  loadRecipe(id) {
    Promise.all([
      callFunction('getRecipeDetail', { id }, { loadingText: '加载清单...' }),
      callFunction('inventory', { action: 'list' }, { loading: false, showError: false }).catch(() => null),
      callFunction('favorites', { action: 'list' }, { loading: false, showError: false }).catch(() => null)
    ])
      .then(([res, invRes, favRes]) => {
        const recipe = res && res.recipe;
        if (!recipe) {
          wx.showToast({ title: '菜谱不存在', icon: 'none' });
          return;
        }
        // 可用库存（排除已过期），用于标注主料「库存/需买」
        const invItems = (invRes && invRes.items) || [];
        const stockList = invItems
          .filter(i => i._status !== 'expired')
          .map(i => ({ name: i.name, expiring: i._status === 'expiring' }));

        const groups = this.buildGroups(recipe, stockList);
        const total = groups.reduce((sum, g) => sum + g.items.length, 0);

        // 统计主料中「库存已有 / 需购买」数量
        let haveCount = 0;
        let buyCount = 0;
        groups.forEach(g => {
          if (g.key !== 'mainIngredients') return;
          g.items.forEach(it => { if (it.have) haveCount += 1; else buyCount += 1; });
        });

        // 当前菜谱是否已收藏
        const favorites = (favRes && favRes.favorites) || [];
        const favorited = favorites.some(f => f.recipeId === id);

        this.setData({ recipe, groups, total, checkedCount: 0, allChecked: total === 0, haveCount, buyCount, favorited });
      })
      .catch(() => {});
  },

  // 将菜谱 checklist 转成分组勾选结构；主料标注库存/需买
  buildGroups(recipe, stockList) {
    const checklist = recipe.checklist || {};
    return GROUP_DEFS.map(def => {
      const raw = checklist[def.key] || [];
      const isMain = def.key === 'mainIngredients';
      return {
        key: def.key,
        title: def.title,
        items: raw.map((text, idx) => {
          const item = {
            id: `${def.key}_${idx}`,
            text,
            checked: false,
            showStock: isMain,
            have: false,
            expiring: false
          };
          if (isMain) {
            const hit = matchStock(text, stockList);
            item.have = !!hit;
            item.expiring = !!(hit && hit.expiring);
          }
          return item;
        })
      };
    }).filter(g => g.items.length > 0);
  },

  onItemChange(e) {
    const { itemId, checked } = e.detail;
    const groups = this.data.groups.map(g => ({
      key: g.key,
      title: g.title,
      items: g.items.map(it =>
        it.id === itemId ? Object.assign({}, it, { checked }) : it
      )
    }));

    let checkedCount = 0;
    groups.forEach(g => g.items.forEach(it => { if (it.checked) checkedCount += 1; }));

    this.setData({
      groups,
      checkedCount,
      allChecked: checkedCount >= this.data.total
    });
  },

  // 进入烹饪导航：未备齐也允许查看步骤，仅做二次确认提醒
  onStartCook() {
    const go = () => {
      app.globalData.currentRecipe = this.data.recipe;
      wx.navigateTo({ url: '/pages/cook/cook' });
    };

    if (this.data.allChecked) {
      go();
      return;
    }

    const remain = this.data.total - this.data.checkedCount;
    wx.showModal({
      title: '还没备齐哦',
      content: `还有 ${remain} 项未备齐，确定现在就进入烹饪步骤吗？`,
      confirmText: '仍要开始',
      cancelText: '继续备菜',
      success: (res) => {
        if (res.confirm) go();
      }
    });
  },

  // 只看烹饪步骤：以预览模式进入时间轴（不锁屏常亮、无二次确认）
  onPreviewSteps() {
    app.globalData.currentRecipe = this.data.recipe;
    wx.navigateTo({ url: '/pages/cook/cook?viewOnly=1' });
  },

  // 收藏 / 取消收藏当前这道菜（乐观更新，失败回滚）
  onToggleFavorite() {
    const recipe = this.data.recipe;
    if (!recipe || !recipe._id) return;
    const favorited = !this.data.favorited;
    const payload = favorited
      ? { action: 'add', recipe }
      : { action: 'remove', recipeId: recipe._id };
    this.setData({ favorited });
    callFunction('favorites', payload, { loading: false, showError: false })
      .then(() => wx.showToast({ title: favorited ? '已收藏' : '已取消收藏', icon: 'none' }))
      .catch(() => this.setData({ favorited: !favorited }));
  }
});
