// cloudfunctions/inventory/index.js
// 轻量库存管理：手动录入/编辑/删除食材，做菜后按 BOM 自动扣减。
// 入参：{ action: 'list'|'save'|'delete'|'deduct', ...payload }
//   - list  : 无额外参数，返回当前用户库存（含状态与临期天数）
//   - save  : { item: { _id?, name, category, quantity, unit, expiryDate } } 新增或更新
//   - delete: { id }
//   - deduct: { recipeId } 按菜谱 ingredientsNeeded 扣减
const cloud = require('wx-server-sdk');

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const db = cloud.database();
const ingCol = db.collection('ingredients');
const recipesCol = db.collection('recipes');

const EXPIRING_DAYS = 2; // 临期阈值：距过期 <= 2 天

function pad(n) {
  return n < 10 ? '0' + n : '' + n;
}

function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// 距过期天数：正数=还有几天，负数=已过期几天，null=无保质期
function daysUntil(dateStr) {
  if (!dateStr) return null;
  const t = new Date(todayStr() + 'T00:00:00').getTime();
  const e = new Date(dateStr + 'T00:00:00').getTime();
  if (isNaN(e)) return null;
  return Math.round((e - t) / 86400000);
}

function statusOf(dateStr) {
  const d = daysUntil(dateStr);
  if (d === null) return 'normal';
  if (d < 0) return 'expired';
  if (d <= EXPIRING_DAYS) return 'expiring';
  return 'normal';
}

// 附加计算字段，便于前端分组展示
function decorate(item) {
  return Object.assign({}, item, {
    _status: statusOf(item.expiryDate),
    _daysLeft: daysUntil(item.expiryDate)
  });
}

async function ensureCollection() {
  await db.createCollection('ingredients').catch(() => {});
}

exports.main = async (event = {}) => {
  const { OPENID } = cloud.getWXContext();
  const action = event.action;

  if (!OPENID) {
    return { code: 1, message: '无法获取 openid' };
  }

  try {
    await ensureCollection();

    if (action === 'list') {
      const res = await ingCol.where({ openid: OPENID }).limit(500).get();
      const items = (res.data || []).map(decorate);
      // 排序：过期 > 临期 > 正常，再按剩余天数升序
      const order = { expired: 0, expiring: 1, normal: 2 };
      items.sort((a, b) => {
        const oa = order[a._status];
        const ob = order[b._status];
        if (oa !== ob) return oa - ob;
        const da = a._daysLeft === null ? 9999 : a._daysLeft;
        const dbb = b._daysLeft === null ? 9999 : b._daysLeft;
        return da - dbb;
      });
      const summary = {
        total: items.length,
        expiring: items.filter(i => i._status === 'expiring').length,
        expired: items.filter(i => i._status === 'expired').length
      };
      return { code: 0, items, summary };
    }

    if (action === 'save') {
      const item = event.item || {};
      if (!item.name || !String(item.name).trim()) {
        return { code: 2, message: '食材名称不能为空' };
      }
      const now = db.serverDate();
      const data = {
        name: String(item.name).trim(),
        category: item.category || 'other',
        quantity: Number(item.quantity) || 1,
        unit: item.unit || '份',
        expiryDate: item.expiryDate || '',
        updatedAt: now
      };

      if (item._id) {
        // 更新（校验归属）
        await ingCol.where({ _id: item._id, openid: OPENID }).update({ data });
        const updated = decorate(Object.assign({ _id: item._id, openid: OPENID }, data));
        return { code: 0, item: updated };
      }

      data.openid = OPENID;
      data.createdAt = now;
      const addRes = await ingCol.add({ data });
      const created = decorate(Object.assign({ _id: addRes._id, openid: OPENID }, data));
      return { code: 0, item: created };
    }

    if (action === 'delete') {
      if (!event.id) return { code: 2, message: '缺少 id' };
      await ingCol.where({ _id: event.id, openid: OPENID }).remove();
      return { code: 0, id: event.id };
    }

    if (action === 'deduct') {
      if (!event.recipeId) return { code: 2, message: '缺少 recipeId' };
      const rRes = await recipesCol.doc(event.recipeId).get().catch(() => null);
      const recipe = rRes && rRes.data;
      if (!recipe) return { code: 3, message: '菜谱不存在' };

      const need = recipe.ingredientsNeeded || [];
      const deducted = [];
      for (const n of need) {
        if (!n || !n.name) continue;
        const found = await ingCol.where({ openid: OPENID, name: n.name }).limit(1).get();
        const doc = found.data && found.data[0];
        if (!doc) continue;
        const remain = (Number(doc.quantity) || 0) - (Number(n.qty) || 0);
        if (remain <= 0) {
          await ingCol.doc(doc._id).remove();
        } else {
          await ingCol.doc(doc._id).update({ data: { quantity: remain, updatedAt: db.serverDate() } });
        }
        deducted.push({ name: n.name, used: n.qty, unit: n.unit, remain: Math.max(0, remain) });
      }
      return { code: 0, deducted };
    }

    return { code: 1, message: '未知 action: ' + action };
  } catch (err) {
    console.error('[inventory] error', err);
    return { code: 4, message: err.message || '库存操作失败' };
  }
};
