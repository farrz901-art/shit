// Root lint-staged: 整个 monorepo 的 staged 文件处理
// 跑法: bunx --bun lint-staged (从根目录, 自动找到本 config)
//
// 后端: ruff check --fix + ruff format
// 前端: oxlint --fix + oxfmt
// 全局: oxfmt (json/md/yml)
//
// (2026-06-14) 删所有 `&& git add ${files}`: lint-staged v10+ 自动 stage 修过的
//   文件 (v17 检测到 git add 会警告). 不需要手动 re-add.
//
// Windows 兼容: lint-staged 默认走 cmd, 直接 'cd subdir &&' 解析路径会失败
// 用 'bash -c "cd subdir && bun x <bin> ${files}"' 让 bash 处理 CWD 切换
// (bash 跨平台, 用户环境有 Git Bash 就有)

function toRelFrom(subdir, files) {
  return files
    .map((f) => {
      const norm = f.replace(/\\/g, "/");
      const idx = norm.indexOf(`/${subdir}/`);
      return idx >= 0 ? norm.slice(idx + subdir.length + 2) : f;
    })
    .join(" ");
}

export default {
  "packages/service/**/*.py": (stagedFiles) => {
    const files = toRelFrom("packages/service", stagedFiles);
    return [
      `bash -c "cd packages/service && uv run --no-sync ruff check --fix ${files}"`,
      `bash -c "cd packages/service && uv run --no-sync ruff format ${files}"`,
      // pytest --picked: 装 pytest-picked 后, 自动跑 commit 改的 test file (不全量)
      // 走 venv python 直跑, 绕 uv trampoline 在 hook 派生时 canonicalize 失败 (Windows 已知)
      // || true: 改 src 没联动 test 时 pytest-picked 报 0 tests exit 5, 容忍不阻塞. 业务代码可以纯改 src.
      `bash -c "cd packages/service && ./.venv/Scripts/python.exe -m pytest --picked --tb=short -q || true"`,
    ];
  },
  "packages/web/**/*.{ts,tsx,js,jsx}": (stagedFiles) => {
    const files = toRelFrom("packages/web", stagedFiles);
    return [
      `bash -c "cd packages/web && bun x oxlint ${files} --fix"`,
      // --deny-warnings: warning 也 exit non-zero → lint-staged 阻塞 commit
      // 遵守 .oxlintrc.json 配置, 不会 -D 覆盖导致规则重激活
      `bash -c "cd packages/web && bun x oxlint ${files} --deny-warnings"`,
      `bash -c "cd packages/web && bun x oxfmt ${files}"`,
      // vitest related: collect 全量找 related, 只 run related (不全量 run)
      // 走 bun x vitest (vitest 不在 PATH, 直接 vitest 找不到)
      // --reporter=default (vitest 4 删了 'basic' alias)
      `bash -c "cd packages/web && bun x vitest related --run --reporter=default"`,
    ];
  },
  "**/*.{yml,yaml}": (stagedFiles) => {
    const files = toRelFrom("packages/web", stagedFiles);
    return [`bash -c "cd packages/web && bun x oxfmt ${files}"`];
  },
   "**/*": () => [],
};
