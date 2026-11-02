// cloudfunctions/login/index.js
// 静默登录：获取 openid，确保 users 集合中存在该用户记录
const cloud = require('wx-server-sdk');

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });

const db = cloud.database();
const usersCol = db.collection('users');

exports.main = async () => {
  const wxContext = cloud.getWXContext();
  const openid = wxContext.OPENID;

  if (!openid) {
    return { code: 1, message: '无法获取 openid' };
  }

  try {
    // 确保 users 集合存在（已存在会抛错，忽略）
    await db.createCollection('users').catch(() => {});

    // users 集合以 openid 作为 _id，天然去重
    const existing = await usersCol.doc(openid).get().catch(() => null);

    let user;
    if (existing && existing.data) {
      user = existing.data;
    } else {
      user = {
        _id: openid,
        openid,
        familyId: '',
        preferences: {
          allergies: [],
          taste: [],
          excludeIngredients: []
        },
        createdAt: db.serverDate(),
        updatedAt: db.serverDate()
      };
      await usersCol.add({ data: user });
    }

    return { code: 0, openid, user };
  } catch (err) {
    console.error('[login] error', err);
    return { code: 2, message: err.message || '登录失败' };
  }
};
