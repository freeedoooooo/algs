// utils/request.js
// 统一封装云函数调用，处理 loading 与错误提示
const { USE_MOCK } = require('../config.js');
const mock = require('../mock');

/**
 * 调用云函数
 * @param {string} name 云函数名
 * @param {object} data 入参
 * @param {object} options { loading: 是否显示 loading, loadingText: 提示文案, showError: 是否弹错误 }
 * @returns {Promise<any>} 云函数 result
 */
function callFunction(name, data = {}, options = {}) {
  const { loading = true, loadingText = '加载中...', showError = true } = options;

  if (loading) {
    wx.showLoading({ title: loadingText, mask: true });
  }

  // Mock 模式：走本地假数据；否则调用真实云函数
  const task = USE_MOCK
    ? mock.callFunction(name, data).then(result => ({ result }))
    : wx.cloud.callFunction({ name, data });

  return task
    .then(res => {
      const result = res && res.result;
      if (result && result.code !== undefined && result.code !== 0) {
        // 业务错误
        throw new Error(result.message || '服务异常');
      }
      return result;
    })
    .catch(err => {
      console.error(`[callFunction:${name}]`, err);
      if (showError) {
        wx.showToast({
          title: (err && err.message) || '网络异常，请重试',
          icon: 'none',
          duration: 2000
        });
      }
      throw err;
    })
    .finally(() => {
      if (loading) {
        wx.hideLoading();
      }
    });
}

module.exports = {
  callFunction
};
