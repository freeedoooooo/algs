// components/recipe-card/recipe-card.js
const { TYPE_LABEL } = require('../../utils/format.js');

Component({
  properties: {
    recipe: {
      type: Object,
      value: {}
    },
    // 是否显示"选择/查看"操作
    selectable: {
      type: Boolean,
      value: false
    },
    // 是否已收藏
    favorited: {
      type: Boolean,
      value: false
    }
  },

  data: {
    typeLabel: '',
    typeClass: 'meat'
  },

  observers: {
    'recipe.type': function (type) {
      this.setData({
        typeLabel: TYPE_LABEL[type] || '菜',
        typeClass: type || 'meat'
      });
    }
  },

  methods: {
    onTap() {
      this.triggerEvent('tap', { recipe: this.data.recipe });
    },
    // 点击星标：切换收藏状态（阻止冒泡到卡片）
    onFavTap() {
      this.triggerEvent('favorite', {
        recipe: this.data.recipe,
        favorited: !this.data.favorited
      });
    }
  }
});
