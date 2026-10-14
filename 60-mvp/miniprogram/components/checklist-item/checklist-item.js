// components/checklist-item/checklist-item.js
Component({
  properties: {
    text: { type: String, value: '' },
    checked: { type: Boolean, value: false },
    // 用于回传的标识
    itemId: { type: String, value: '' }
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
