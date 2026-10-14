// cloudfunctions/recommendMenu/index.js
// AI 一键推荐菜单：按场景 + 时令从预置菜谱库中组合出 1荤1素1汤
// 入参：{ scene: 'quick'|'easy'|'feast', month: 1-12, preferences: {excludeIngredients,allergies,taste} }
const cloud = require('wx-server-sdk');
const { chatJSON } = require('./ai.js');

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const db = cloud.database();
const recipesCol = db.collection('recipes');

// 按类型分组
function groupByType(list) {
  const g = { meat: [], vegetable: [], soup: [] };
  list.forEach(r => {
    if (g[r.type]) g[r.type].push(r);
  });
  return g;
}

function pickRandom(arr) {
  if (!arr.length) return null;
  return arr[Math.floor(Math.random() * arr.length)];
}

// 过滤掉命中忌口/过敏/排除食材的菜谱
function applyPreferences(list, preferences = {}) {
  const exclude = []
    .concat(preferences.excludeIngredients || [])
    .concat(preferences.allergies || []);
  if (!exclude.length) return list;
  return list.filter(r => {
    const names = (r.ingredientsNeeded || []).map(i => i.name).join(',');
    return !exclude.some(e => e && names.includes(e));
  });
}

// 兜底：从各类型随机取一道
function fallbackMenu(groups) {
  const menu = [];
  const meat = pickRandom(groups.meat);
  const veg = pickRandom(groups.vegetable);
  const soup = pickRandom(groups.soup);
  if (meat) menu.push(meat);
  if (veg) menu.push(veg);
  if (soup) menu.push(soup);
  return menu;
}

exports.main = async (event = {}) => {
  const scene = event.scene || 'easy';
  const month = event.month || new Date().getMonth() + 1;
  const preferences = event.preferences || {};

  try {
    // 1. 按场景标签查候选池
    const res = await recipesCol.where({ tags: scene }).limit(100).get();
    let scenePool = res.data || [];

    if (!scenePool.length) {
      return { code: 3, message: '菜谱库为空，请先执行 seed 云函数初始化数据' };
    }

    // 2. 时令过滤（JS 侧，数据量小；空 season 视为全年）
    let pool = scenePool.filter(
      r => !r.season || r.season.length === 0 || r.season.includes(month)
    );
    if (pool.length < 3) pool = scenePool; // 时令命中过少则放宽

    // 3. 偏好过滤
    pool = applyPreferences(pool, preferences);
    if (pool.length < 3) pool = applyPreferences(scenePool, preferences);

    const groups = groupByType(pool);

    // 4. AI 组合推荐
    let menu = [];
    let reason = '';
    let source = 'fallback';

    const catalog = {
      meat: groups.meat.map(r => r.name),
      vegetable: groups.vegetable.map(r => r.name),
      soup: groups.soup.map(r => r.name)
    };

    const aiResult = await chatJSON(
      '你是一个家庭营养搭餐助手。只能从用户提供的候选菜名中选择，禁止编造。返回严格的 JSON。',
      `当前月份${month}月，场景「${scene}」。请从以下候选中各选一道组成一荤一素一汤的合理搭配：\n` +
        `荤菜候选：${catalog.meat.join('、') || '无'}\n` +
        `素菜候选：${catalog.vegetable.join('、') || '无'}\n` +
        `汤候选：${catalog.soup.join('、') || '无'}\n` +
        `返回格式：{"meat":"菜名","vegetable":"菜名","soup":"菜名","reason":"一句话搭配理由"}`
    );

    if (aiResult) {
      const byName = {};
      pool.forEach(r => { byName[r.name] = r; });
      const picked = [
        byName[aiResult.meat],
        byName[aiResult.vegetable],
        byName[aiResult.soup]
      ].filter(Boolean);

      // 校验类型齐全，缺失的用兜底补齐
      const pickedTypes = picked.map(r => r.type);
      if (!pickedTypes.includes('meat') && groups.meat.length) picked.push(pickRandom(groups.meat));
      if (!pickedTypes.includes('vegetable') && groups.vegetable.length) picked.push(pickRandom(groups.vegetable));
      if (!pickedTypes.includes('soup') && groups.soup.length) picked.push(pickRandom(groups.soup));

      if (picked.length) {
        menu = picked;
        reason = aiResult.reason || '';
        source = 'ai';
      }
    }

    // 5. 兜底
    if (!menu.length) {
      menu = fallbackMenu(groups);
      reason = '为你随机搭配了均衡的一餐';
      source = 'fallback';
    }

    return {
      code: 0,
      scene,
      month,
      source,
      reason,
      menu: menu.map(r => ({
        _id: r._id,
        name: r.name,
        type: r.type,
        tags: r.tags,
        estimatedTime: r.estimatedTime,
        servings: r.servings,
        tip: r.tip
      }))
    };
  } catch (err) {
    console.error('[recommendMenu] error', err);
    return { code: 1, message: err.message || '推荐失败' };
  }
};
