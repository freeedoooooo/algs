// cloudfunctions/getRecipeDetail/index.js
// 获取菜谱详情（含 checklist 与 timelineSteps）
// 入参：{ id: 'recipe_xxx' } 或 { ids: ['recipe_xxx', ...] }
const cloud = require('wx-server-sdk');

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const db = cloud.database();
const _ = db.command;
const recipesCol = db.collection('recipes');

exports.main = async (event = {}) => {
  const { id, ids } = event;

  try {
    // 单个查询
    if (id) {
      const res = await recipesCol.doc(id).get().catch(() => null);
      if (!res || !res.data) {
        return { code: 2, message: '菜谱不存在' };
      }
      return { code: 0, recipe: res.data };
    }

    // 批量查询
    if (Array.isArray(ids) && ids.length) {
      const res = await recipesCol.where({ _id: _.in(ids) }).limit(50).get();
      // 保持与入参顺序一致
      const map = {};
      (res.data || []).forEach(r => { map[r._id] = r; });
      const recipes = ids.map(i => map[i]).filter(Boolean);
      return { code: 0, recipes };
    }

    return { code: 1, message: '缺少 id 或 ids 参数' };
  } catch (err) {
    console.error('[getRecipeDetail] error', err);
    return { code: 1, message: err.message || '查询失败' };
  }
};
