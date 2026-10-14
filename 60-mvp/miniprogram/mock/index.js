// miniprogram/mock/index.js
// 本地 Mock 云函数：在 USE_MOCK=true 时替代真实云函数，返回相同结构的数据。
// 覆盖 login / recommendMenu / getRecipeDetail / seed 四个函数。
const { recipes } = require('./recipes.js');

// 模拟网络延迟
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function pickRandom(arr) {
  if (!arr.length) return null;
  return arr[Math.floor(Math.random() * arr.length)];
}

function groupByType(list) {
  const g = { meat: [], vegetable: [], soup: [] };
  list.forEach(r => { if (g[r.type]) g[r.type].push(r); });
  return g;
}

// 摘要字段（与云函数 recommendMenu 返回结构一致）
function toSummary(r) {
  return {
    _id: r._id,
    name: r.name,
    type: r.type,
    tags: r.tags,
    estimatedTime: r.estimatedTime,
    servings: r.servings,
    tip: r.tip
  };
}

const handlers = {
  // 静默登录
  login() {
    return {
      code: 0,
      openid: 'mock_openid',
      user: {
        _id: 'mock_openid',
        preferences: { allergies: [], taste: [], excludeIngredients: [] }
      }
    };
  },

  // 菜谱详情
  getRecipeDetail(data = {}) {
    const { id, ids } = data;
    if (id) {
      const r = recipes.find(x => x._id === id);
      return r ? { code: 0, recipe: r } : { code: 2, message: '菜谱不存在' };
    }
    if (Array.isArray(ids) && ids.length) {
      const map = {};
      recipes.forEach(r => { map[r._id] = r; });
      return { code: 0, recipes: ids.map(i => map[i]).filter(Boolean) };
    }
    return { code: 1, message: '缺少 id 或 ids 参数' };
  },

  // AI 推荐菜单（Mock 版：场景+时令筛选后随机组合，不调用大模型）
  recommendMenu(data = {}) {
    const scene = data.scene || 'easy';
    const month = data.month || (new Date().getMonth() + 1);

    let scenePool = recipes.filter(r => (r.tags || []).includes(scene));
    if (!scenePool.length) {
      return { code: 3, message: '菜谱库为空' };
    }

    // 时令过滤（空 season 视为全年）
    let pool = scenePool.filter(
      r => !r.season || r.season.length === 0 || r.season.includes(month)
    );
    if (pool.length < 3) pool = scenePool;

    const groups = groupByType(pool);
    const menu = [
      pickRandom(groups.meat),
      pickRandom(groups.vegetable),
      pickRandom(groups.soup)
    ].filter(Boolean);

    return {
      code: 0,
      scene,
      month,
      source: 'mock',
      reason: '（Mock 模式）为你随机搭配了均衡的一荤一素一汤',
      menu: menu.map(toSummary)
    };
  },

  // Mock 模式无需初始化数据
  seed() {
    return { code: 0, message: 'Mock 模式使用内置数据，无需 seed', total: recipes.length };
  }
};

/**
 * 模拟 wx.cloud.callFunction
 * @returns {Promise<object>} 直接返回 result 对象
 */
function callFunction(name, data = {}) {
  const handler = handlers[name];
  return delay(300).then(() => {
    if (!handler) {
      return { code: 1, message: '未知云函数(Mock): ' + name };
    }
    return handler(data);
  });
}

module.exports = { callFunction };
