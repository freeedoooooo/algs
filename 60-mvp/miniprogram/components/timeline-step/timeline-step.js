// components/timeline-step/timeline-step.js
const { STEP_TYPE_LABEL } = require('../../utils/format.js');

Component({
  properties: {
    index: { type: Number, value: 0 },
    step: { type: Object, value: {} },
    // pending | running | done
    status: { type: String, value: 'pending' },
    // 倒计时展示文本（running 时有效）
    remainText: { type: String, value: '' },
    // 预览模式：只展示步骤，隐藏倒计时/完成等操作按钮
    viewOnly: { type: Boolean, value: false }
  },

  data: {
    typeLabel: '烹'
  },

  observers: {
    'step.type': function (type) {
      this.setData({ typeLabel: STEP_TYPE_LABEL[type] || '烹' });
    }
  },

  methods: {
    onStart() {
      this.triggerEvent('start', { index: this.data.index });
    },
    onDone() {
      this.triggerEvent('done', { index: this.data.index });
    }
  }
});
