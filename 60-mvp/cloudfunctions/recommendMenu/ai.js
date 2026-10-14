// cloudfunctions/recommendMenu/ai.js
// AI 能力抽象层：默认接入通义千问(DashScope OpenAI 兼容模式)
// 后续如需切换腾讯混元等，只需替换 chatJSON 的实现，保持接口不变。
const axios = require('axios');

const DASHSCOPE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions';
// 可通过云函数环境变量覆盖模型，默认 qwen-turbo（速度快、成本低）
const MODEL = process.env.QWEN_MODEL || 'qwen-turbo';
const TIMEOUT = Number(process.env.AI_TIMEOUT || 8000);

/**
 * 调用大模型并期望返回 JSON
 * @param {string} systemPrompt 系统提示
 * @param {string} userPrompt 用户提示
 * @returns {Promise<object|null>} 解析后的 JSON 对象；失败返回 null（由调用方兜底）
 */
async function chatJSON(systemPrompt, userPrompt) {
  const apiKey = process.env.DASHSCOPE_API_KEY;
  if (!apiKey) {
    console.warn('[ai] 未配置 DASHSCOPE_API_KEY，跳过 AI，走兜底逻辑');
    return null;
  }

  try {
    const resp = await axios.post(
      DASHSCOPE_URL,
      {
        model: MODEL,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt }
        ],
        temperature: 0.8,
        response_format: { type: 'json_object' }
      },
      {
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        timeout: TIMEOUT
      }
    );

    const content =
      resp.data &&
      resp.data.choices &&
      resp.data.choices[0] &&
      resp.data.choices[0].message &&
      resp.data.choices[0].message.content;

    if (!content) return null;
    return JSON.parse(content);
  } catch (err) {
    console.error('[ai] 调用失败，走兜底逻辑：', err.message);
    return null;
  }
}

module.exports = { chatJSON };
