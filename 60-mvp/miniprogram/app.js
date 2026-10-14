// app.js
App({
  globalData: {
    // 云开发环境 ID，请在开通云开发后填入你自己的 env ID
    // 留空则使用默认环境（首个创建的环境）
    env: '',
    openid: '',
    userInfo: null
  },

  onLaunch() {
    if (!wx.cloud) {
      console.error('请使用 2.2.3 或以上的基础库以使用云能力');
      return;
    }

    wx.cloud.init({
      env: this.globalData.env || undefined,
      traceUser: true
    });

    // 静默登录，获取 openid 并确保 users 记录存在
    this.silentLogin();
  },

  silentLogin() {
    wx.cloud.callFunction({ name: 'login' })
      .then(res => {
        const { openid, user } = res.result || {};
        this.globalData.openid = openid || '';
        this.globalData.userInfo = user || null;
        console.log('[login] openid =', openid);
      })
      .catch(err => {
        console.error('[login] 调用失败', err);
      });
  }
});
