// pages/inventory/inventory.js
const { callFunction } = require('../../utils/request.js');
const { ING_CATEGORIES, CATEGORY_LABEL, STATUS_META } = require('../../utils/format.js');

// 分组展示顺序：过期 > 临期 > 新鲜
const SECTION_ORDER = [
  { status: 'expired', title: '🔴 已过期' },
  { status: 'expiring', title: '🟡 临期（2天内）' },
  { status: 'normal', title: '🟢 新鲜' }
];

const EMPTY_FORM = {
  _id: '',
  name: '',
  categoryIndex: 4,
  quantity: '1',
  unit: '份',
  expiryDate: ''
};

Page({
  data: {
    sections: [],
    summary: { total: 0, expiring: 0, expired: 0 },
    categoryLabels: ING_CATEGORIES.map(c => c.label),
    formVisible: false,
    editing: false,
    form: Object.assign({}, EMPTY_FORM)
  },

  onShow() {
    this.loadList();
  },

  loadList() {
    callFunction('inventory', { action: 'list' }, { loadingText: '加载库存...' })
      .then(res => {
        const items = (res && res.items) || [];
        const summary = (res && res.summary) || { total: 0, expiring: 0, expired: 0 };
        const sections = SECTION_ORDER.map(sec => ({
          status: sec.status,
          title: sec.title,
          color: (STATUS_META[sec.status] || {}).color,
          items: items
            .filter(i => i._status === sec.status)
            .map(i => Object.assign({}, i, {
              categoryLabel: CATEGORY_LABEL[i.category] || '🧺 其他',
              expiryText: i.expiryDate || '无保质期',
              statusText: this.statusText(i)
            }))
        })).filter(s => s.items.length > 0);
        this.setData({ sections, summary });
      })
      .catch(() => {});
  },

  // 状态文案：还剩 N 天 / 已过期 N 天 / 今天到期
  statusText(item) {
    if (item._daysLeft === null || item._daysLeft === undefined) return '无保质期';
    if (item._daysLeft === 0) return '今天到期';
    if (item._daysLeft < 0) return `已过期 ${Math.abs(item._daysLeft)} 天`;
    return `还剩 ${item._daysLeft} 天`;
  },

  onAdd() {
    this.setData({ formVisible: true, editing: false, form: Object.assign({}, EMPTY_FORM) });
  },

  onEditItem(e) {
    const item = e.currentTarget.dataset.item;
    const idx = ING_CATEGORIES.findIndex(c => c.key === item.category);
    this.setData({
      formVisible: true,
      editing: true,
      form: {
        _id: item._id,
        name: item.name,
        categoryIndex: idx >= 0 ? idx : 4,
        quantity: String(item.quantity),
        unit: item.unit || '份',
        expiryDate: item.expiryDate || ''
      }
    });
  },

  onCloseForm() {
    this.setData({ formVisible: false });
  },

  onFormInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: e.detail.value });
  },

  onCategoryChange(e) {
    this.setData({ 'form.categoryIndex': Number(e.detail.value) });
  },

  onDateChange(e) {
    this.setData({ 'form.expiryDate': e.detail.value });
  },

  onClearDate() {
    this.setData({ 'form.expiryDate': '' });
  },

  onSave() {
    const f = this.data.form;
    if (!f.name || !f.name.trim()) {
      wx.showToast({ title: '请输入食材名称', icon: 'none' });
      return;
    }
    const item = {
      name: f.name.trim(),
      category: (ING_CATEGORIES[f.categoryIndex] || {}).key || 'other',
      quantity: Number(f.quantity) || 1,
      unit: (f.unit || '份').trim(),
      expiryDate: f.expiryDate || ''
    };
    if (f._id) item._id = f._id;

    callFunction('inventory', { action: 'save', item }, { loadingText: '保存中...' })
      .then(() => {
        this.setData({ formVisible: false });
        wx.showToast({ title: '已保存', icon: 'success' });
        this.loadList();
      })
      .catch(() => {});
  },

  onDelete() {
    const id = this.data.form._id;
    if (!id) {
      this.setData({ formVisible: false });
      return;
    }
    wx.showModal({
      title: '删除食材',
      content: `确定删除「${this.data.form.name}」吗？`,
      confirmColor: '#E53935',
      success: (res) => {
        if (!res.confirm) return;
        callFunction('inventory', { action: 'delete', id }, { loadingText: '删除中...' })
          .then(() => {
            this.setData({ formVisible: false });
            wx.showToast({ title: '已删除', icon: 'success' });
            this.loadList();
          })
          .catch(() => {});
      }
    });
  }
});
