// cloudfunctions/seed/index.js
// 一次性初始化种子菜谱数据到 recipes 集合
// 调用方式：在云开发控制台或小程序端调用 seed 云函数（幂等，可重复执行）
const cloud = require('wx-server-sdk');
const { recipes } = require('./recipes.js');

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const db = cloud.database();
const recipesCol = db.collection('recipes');

exports.main = async (event = {}) => {
  const { mode = 'upsert' } = event; // upsert: 按 _id 覆盖; clear: 先清空再写入

  try {
    // 确保集合存在（不存在则创建，已存在会抛错，忽略即可）
    await db.createCollection('recipes').catch(() => {});

    if (mode === 'clear') {
      // 清空现有数据（分批删除，云数据库单次删除上限 100 条）
      let deleted = 0;
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const res = await recipesCol.limit(100).get();
        if (!res.data.length) break;
        await Promise.all(res.data.map(d => recipesCol.doc(d._id).remove()));
        deleted += res.data.length;
      }
      console.log('[seed] cleared', deleted);
    }

    let success = 0;
    let failed = 0;
    for (const item of recipes) {
      const doc = Object.assign({}, item);
      const id = doc._id;
      try {
        // 尝试更新，不存在则新增
        const existing = await recipesCol.doc(id).get().catch(() => null);
        if (existing && existing.data) {
          delete doc._id;
          await recipesCol.doc(id).update({ data: doc });
        } else {
          await recipesCol.add({ data: item });
        }
        success += 1;
      } catch (e) {
        failed += 1;
        console.error('[seed] item failed', id, e.message);
      }
    }

    return { code: 0, total: recipes.length, success, failed, mode };
  } catch (err) {
    console.error('[seed] error', err);
    return { code: 1, message: err.message || 'seed 失败' };
  }
};
