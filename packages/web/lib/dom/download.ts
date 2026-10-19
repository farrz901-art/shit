// 浏览器原生下载工具 (2026-06-11)
// 拿一个 blob + filename, 创建 object URL, 触发 <a download> 点击, 释放 URL
// 用途: BFF 鉴权后端流式返回 (zip/csv/excel) 时, fetch+authHeaders 拿 blob
// 不能再用 <a href download>: 浏览器原生导航不带自定义头 → 后端 401
/**
 * 触发浏览器下载 blob 文件
 * @param blob     二进制数据
 * @param filename 下载文件名
 *
 * 调用边界:
 *   @client-bff  前端组件可用 (调 /api/* BFF)
 */
// eslint-disable-next-line max-statements -- DOM 操作顺序执行, 拆分函数不降低成本
export const triggerBrowserDownload = (blob: Blob, filename: string): void => {
  if (typeof globalThis === "undefined") {
    return;
  }
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    // AppendChild 在 Firefox 上必需要, click 才生效
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  } finally {
    // 给浏览器一拍时间真触发下载, 再释放; 立刻 revoke 大文件可能丢
    // eslint-disable-next-line no-magic-numbers -- setTimeout 0 拍浏览器微任务
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
};
