// cloudfunctions/favorites/index.js
// 菜谱收藏：收藏 / 列出 / 取消收藏「单个菜谱」（一个菜一个菜地做）。
// 入参：{ action: 'list'|'add'|'remove', ...payload }
//   - list  : 返回当前用户收藏的菜谱（按收藏时间倒序）
//   - add   : { recipe: { _id, name, type, estimatedTime, servings, tip } }，按 recipeId 去重
//   - remove: { recipeId } 取消收藏
const cloud = require('wx-server-sdk');

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const db = cloud.database();
const col = db.collection('favorites');

async function ensureCollection() {
  await db.createCollection('favorites').catch(() => {});
}

exports.main = async (event = {}) => {
  const { OPENID } = cloud.getWXContext();
  const action = event.action;

  if (!OPENID) return { code: 1, message: '无法获取 openid' };

  try {
    await ensureCollection();

    if (action === 'list') {
      const res = await col.where({ openid: OPENID }).orderBy('createdAt', 'desc').limit(200).get();
      return { code: 0, favorites: res.data || [] };
    }

    if (action === 'add') {
      const r = event.recipe || {};
      const recipeId = r._id || r.recipeId;
      if (!recipeId) return { code: 2, message: '缺少菜谱 ID' };
      // 去重：已收藏则直接返回
      const exist = await col.where({ openid: OPENID, recipeId }).limit(1).get();
      if (exist.data && exist.data.length) {
        return { code: 0, recipeId, duplicated: true };
      }
      await col.add({
        data: {
          openid: OPENID,
          recipeId,
          name: r.name || '',
          type: r.type || '',
          estimatedTime: r.estimatedTime || 0,
          servings: r.servings || 0,
          tip: r.tip || '',
          createdAt: db.serverDate()
        }
      });
      return { code: 0, recipeId };
    }

    if (action === 'remove') {
      const recipeId = event.recipeId;
      if (!recipeId) return { code: 2, message: '缺少 recipeId' };
      await col.where({ openid: OPENID, recipeId }).remove();
      return { code: 0, recipeId };
    }

    return { code: 1, message: '未知 action: ' + action };
  } catch (err) {
    console.error('[favorites] error', err);
    return { code: 4, message: err.message || '收藏操作失败' };
  }
};
