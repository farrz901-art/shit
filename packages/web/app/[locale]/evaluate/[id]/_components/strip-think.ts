// (2026-06-11) 共享: 删 Dify answer 中的 <think>...</think> 推理块
// 前端展示时用 (后端 DifyClient.achat 返 answer 时也会 strip, 这里是兜底: 历史评估入库时
// _strip_think 还没加, DB 存的是原文, 表格展示时再 strip 一次保证 UI 干净)
/** stripThink - 删除 Dify answer 中的 <think>...</think> 推理块
 * @param answer - 原始 answer 文本
 * @returns 去除推理块后的文本
 * @shared
 */
export const stripThink = (answer: string | null | undefined): string => {
  if (!answer) {
    return "";
  }
  return answer.replace(/<think>.*?<\/think>/gs, "").trim();
};
