// pages/prep/prep.js
const app = getApp();
const { callFunction } = require('../../utils/request.js');

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
    allChecked: false
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
    callFunction('getRecipeDetail', { id }, { loadingText: '加载清单...' })
      .then(res => {
        const recipe = res && res.recipe;
        if (!recipe) {
          wx.showToast({ title: '菜谱不存在', icon: 'none' });
          return;
        }
        const groups = this.buildGroups(recipe);
        const total = groups.reduce((sum, g) => sum + g.items.length, 0);
        this.setData({ recipe, groups, total, checkedCount: 0, allChecked: total === 0 });
      })
      .catch(() => {});
  },

  // 将菜谱 checklist 转成分组勾选结构
  buildGroups(recipe) {
    const checklist = recipe.checklist || {};
    return GROUP_DEFS.map(def => {
      const raw = checklist[def.key] || [];
      return {
        key: def.key,
        title: def.title,
        items: raw.map((text, idx) => ({
          id: `${def.key}_${idx}`,
          text,
          checked: false
        }))
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

  // 全部备齐，进入烹饪导航
  onStartCook() {
    if (!this.data.allChecked) {
      wx.showToast({ title: '还有未备齐的项', icon: 'none' });
      return;
    }
    app.globalData.currentRecipe = this.data.recipe;
    wx.navigateTo({ url: '/pages/cook/cook' });
  }
});
