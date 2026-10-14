// components/checklist-item/checklist-item.js
Component({
  properties: {
    text: { type: String, value: '' },
    checked: { type: Boolean, value: false },
    // 用于回传的标识
    itemId: { type: String, value: '' },
    // 是否展示库存彽标（仅主料组）
    showStock: { type: Boolean, value: false },
    // 库存已有
    have: { type: Boolean, value: false },
    // 库存且临期
    expiring: { type: Boolean, value: false }
  },

  methods: {
    onToggle() {
      this.triggerEvent('change', {
        itemId: this.data.itemId,
        checked: !this.data.checked
      });
    }
  }
});
