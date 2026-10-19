---
name: project-mineru-docker-integration
description: mineru Docker 集成的所有踩坑 — backend 选型、输出布局、resolve_md_path 设计
metadata: 
  node_type: memory
  type: project
  originSessionId: d5923208-4647-4dd0-9acb-40426948d1ee
---

**mineru 镜像：** `mineru:latest`（已存在于用户环境，53.2GB）

**mineru 实际输出布局（已用真实端到端测试验证）：**
```
<output_dir>/<pdf_stem>/<method>/<pdf_stem>.md
       ↓          ↓        ↓         ↓
   输出目录   PDF 文件名  解析方法  真正的 md
```

**关键点：嵌套目录名是 PDF stem（不是输入目录 basename）。** 早期我把它猜成 `input_dir_basename` 错了。

**关键参数：**
- `-p /app/input` `-o /app/output` — 容器内路径
- `-b pipeline` — **CPU 友好的 backend**；VLM/hybrid-* backend 需要 CUDA
- `-m auto` — 解析方法（auto/txt/ocr），默认 auto
- **必须传 `device_requests=[DeviceRequest(count=-1, capabilities=[["gpu"]])]`** — 没传则容器内 CUDA 不可用，即使主机有 RTX 4060（见 [[feedback-docker-gpu-needs-device-requests]]）

**代码位置：**
- `src/pdf_processor/converters/__init__.py::MineruConverter`
- 关键方法：
  - `resolve_md_path(pdf_path, output_dir, method="auto")` — 纯函数，返回正确 md 路径
  - `convert_batch(pdf_paths, output_dir)` — 真跑 docker 容器，**传 device_requests 透传 GPU**
  - `_find_md_in_subdirs(output_dir, pdf_stem)` — 兜底，递归搜同名 md

**踩过的坑（详见相关 memory）：**
- [[feedback-no-mock-for-external-systems]] — 第一次用 mock 测试就声称修好，实际是错的
- [[feedback-verify-with-import-not-pip]] — 误判 docker 库没装
- [[feedback-docker-gpu-needs-device-requests]] — 误判"无 GPU"，实际是容器没拿到 GPU
- [[feedback-debug-distinguish-root-causes]] — 把不同根因混为一谈，下错结论
- 第一次猜嵌套目录是 `input_dir_basename` 错了，应该是 `pdf_stem`

**端到端测试：**
- `tests/test_converters.py::TestMineruEndToEnd::test_real_mineru_generates_and_reads_markdown`
- 默认 skip（`RUN_SLOW_TESTS=1` 开启），跑真实容器+真实 PDF，~55s
- 真接读 `pdfs/magazine_TheEconomist.2024.02.24_page_076.pdf` 测通
