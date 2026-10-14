// components/float-timer/float-timer.js
// 悬浮倒计时：展示当前所有进行中的计时节点
Component({
  properties: {
    // [{ key, label, remainText, urgent }]
    items: { type: Array, value: [] }
  },

  methods: {
    onTapItem(e) {
      const { key } = e.currentTarget.dataset;
      this.triggerEvent('tapitem', { key });
    }
  }
});
