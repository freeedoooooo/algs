// miniprogram/mock/index.js
// 本地 Mock 云函数：在 USE_MOCK=true 时替代真实云函数，返回相同结构的数据。
// 覆盖 login / recommendMenu / getRecipeDetail / inventory / seed 函数。
const { recipes } = require('./recipes.js');
const { ingStatus, daysUntil, dateAfter } = require('../utils/format.js');

// 库存本地持久化 key
const STORE_KEY = 'mock_inventory';

// 首次运行写入几条演示食材，便于体验临期/清库存推荐
function defaultInventory() {
  return [
    { _id: 'ing_seed_1', name: '番茄', category: 'vegetable', quantity: 3, unit: '个', expiryDate: dateAfter(1) },
    { _id: 'ing_seed_2', name: '鸡蛋', category: 'meat', quantity: 6, unit: '个', expiryDate: dateAfter(10) },
    { _id: 'ing_seed_3', name: '黄瓜', category: 'vegetable', quantity: 2, unit: '根', expiryDate: dateAfter(2) },
    { _id: 'ing_seed_4', name: '青椒', category: 'vegetable', quantity: 4, unit: '个', expiryDate: dateAfter(5) },
    { _id: 'ing_seed_5', name: '西兰花', category: 'vegetable', quantity: 1, unit: '颗', expiryDate: dateAfter(3) }
  ];
}

function writeStore(list) {
  try { wx.setStorageSync(STORE_KEY, list); } catch (e) {}
}

function readStore() {
  try {
    const raw = wx.getStorageSync(STORE_KEY);
    if (Array.isArray(raw)) return raw;
  } catch (e) {}
  const seeded = defaultInventory();
  writeStore(seeded);
  return seeded;
}

function genId() {
  return 'ing_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
}

function decorate(item) {
  return Object.assign({}, item, {
    _status: ingStatus(item.expiryDate),
    _daysLeft: daysUntil(item.expiryDate)
  });
}

// 名称模糊匹配
function nameMatch(names, ingName) {
  if (!ingName) return false;
  return names.some(k => k === ingName || k.includes(ingName) || ingName.includes(k));
}

// 菜谱库存消耗得分
function scoreRecipe(r, inv) {
  if (!inv) return 0;
  let s = 0;
  (r.ingredientsNeeded || []).forEach(i => {
    if (nameMatch(inv.expiring, i.name)) s += 2;
    else if (nameMatch(inv.onHand, i.name)) s += 1;
  });
  return s;
}

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

  // AI 推荐菜单（Mock 版：场景+时令筛选后组合，支持清库存优先，不调用大模型）
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

    // 清库存优先：构造库存索引
    const preferInventory = !!data.preferInventory;
    const inventory = Array.isArray(data.inventory) ? data.inventory : [];
    const inv = preferInventory && inventory.length
      ? {
          onHand: inventory.map(i => i.name),
          expiring: inventory.filter(i => i.expiring).map(i => i.name)
        }
      : null;

    // 在评分最高的一批中随机选，兼顾优先与「换一换」多样性
    const pick = arr => {
      if (!arr || !arr.length) return null;
      if (!inv) return pickRandom(arr);
      let best = -1;
      arr.forEach(r => { const s = scoreRecipe(r, inv); if (s > best) best = s; });
      return pickRandom(arr.filter(r => scoreRecipe(r, inv) === best));
    };

    const menu = [
      pick(groups.meat),
      pick(groups.vegetable),
      pick(groups.soup)
    ].filter(Boolean);

    return {
      code: 0,
      scene,
      month,
      source: 'mock',
      reason: inv
        ? '（Mock 模式）优先消耗你的库存/临期食材，搭配了一荤一素一汤'
        : '（Mock 模式）为你随机搭配了均衡的一荤一素一汤',
      menu: menu.map(toSummary)
    };
  },

  // 库存增删改查 + 做菜扣减（本地持久化）
  inventory(data = {}) {
    const action = data.action;
    let list = readStore();

    if (action === 'list') {
      const items = list.map(decorate);
      const order = { expired: 0, expiring: 1, normal: 2 };
      items.sort((a, b) => {
        if (order[a._status] !== order[b._status]) return order[a._status] - order[b._status];
        const da = a._daysLeft === null ? 9999 : a._daysLeft;
        const db = b._daysLeft === null ? 9999 : b._daysLeft;
        return da - db;
      });
      return {
        code: 0,
        items,
        summary: {
          total: items.length,
          expiring: items.filter(i => i._status === 'expiring').length,
          expired: items.filter(i => i._status === 'expired').length
        }
      };
    }

    if (action === 'save') {
      const item = data.item || {};
      if (!item.name || !String(item.name).trim()) {
        return { code: 2, message: '食材名称不能为空' };
      }
      const clean = {
        name: String(item.name).trim(),
        category: item.category || 'other',
        quantity: Number(item.quantity) || 1,
        unit: item.unit || '份',
        expiryDate: item.expiryDate || ''
      };
      if (item._id) {
        list = list.map(x => (x._id === item._id ? Object.assign({}, x, clean) : x));
        writeStore(list);
        return { code: 0, item: decorate(list.find(x => x._id === item._id)) };
      }
      const created = Object.assign({ _id: genId() }, clean);
      list.push(created);
      writeStore(list);
      return { code: 0, item: decorate(created) };
    }

    if (action === 'delete') {
      if (!data.id) return { code: 2, message: '缺少 id' };
      list = list.filter(x => x._id !== data.id);
      writeStore(list);
      return { code: 0, id: data.id };
    }

    if (action === 'deduct') {
      const recipe = recipes.find(r => r._id === data.recipeId);
      if (!recipe) return { code: 3, message: '菜谱不存在' };
      const need = recipe.ingredientsNeeded || [];
      const deducted = [];
      need.forEach(n => {
        if (!n || !n.name) return;
        const idx = list.findIndex(x => x.name === n.name);
        if (idx < 0) return;
        const remain = (Number(list[idx].quantity) || 0) - (Number(n.qty) || 0);
        if (remain <= 0) {
          list.splice(idx, 1);
        } else {
          list[idx] = Object.assign({}, list[idx], { quantity: remain });
        }
        deducted.push({ name: n.name, used: n.qty, unit: n.unit, remain: Math.max(0, remain) });
      });
      writeStore(list);
      return { code: 0, deducted };
    }

    return { code: 1, message: '未知 action(Mock): ' + action };
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
