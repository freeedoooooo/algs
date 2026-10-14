// config.js
// 全局运行配置
module.exports = {
  // 本地 Mock 模式开关
  // true  = 不调用云函数，使用前端内置假数据，可完全离线跑通「推荐→选菜→备菜→时间轴倒计时」闭环
  // false = 走真实微信云开发（云函数 + 云数据库），需已部署云函数并执行 seed 初始化
  // 部署上线前请改为 false
  USE_MOCK: true
};
