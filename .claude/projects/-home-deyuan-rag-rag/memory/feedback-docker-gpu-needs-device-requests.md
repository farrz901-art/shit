---
name: feedback-docker-gpu-needs-device-requests
description: Docker Python SDK 的 containers.run() 默认不传 GPU，必须显式给 device_requests，否则容器内 CUDA 不可用
metadata: 
  node_type: memory
  type: feedback
  originSessionId: d5923208-4647-4dd0-9acb-40426948d1ee
---

**错误：** 在 [[project-mineru-docker-integration]] 调试中，用户明明有 RTX 4060 显卡，但 mineru 容器内 `torch.cuda.is_available()` 一直是 False。我之前下的结论是"无 GPU 时 exit 1"——**错的**，主机有 GPU，是代码没把它透传给容器。

**为什么犯这个错：**
- 我把"主机有 GPU"和"容器能用到 GPU"当成了同一件事
- 没意识到 docker-py SDK 的 `containers.run()` **不会**自动透传 GPU
- 看到 "CUDA not available" 日志就直接归因为"环境没 GPU"，没去验证是不是透传失败
- 没区分两种根本不同的情况：(a) 主机真没 GPU (b) 容器没被授 GPU 权限

**真相：**
- `docker run` 没加 `--gpus all` → 容器内 `/dev/nvidia*` 不存在 → torch 看不到
- `docker run --gpus all` → 容器内 nvidia-smi 能看到 GPU → torch CUDA 可用
- docker-py SDK 等价：必须传 `device_requests=[DeviceRequest(count=-1, capabilities=[["gpu"]])]`

**教训：**
- 看到"CUDA not available"或"GPU not found"时，**先**在容器内手动跑 `nvidia-smi` 和 `python -c "import torch; print(torch.cuda.is_available())"`，区分是 (a) 主机没 GPU (b) 容器没拿到 GPU
- 任何用 docker SDK 跑 GPU 容器的代码，都必须检查是否传了 `device_requests`
- "环境没 GPU"是个甩锅型的诊断，**先查容器内能不能看到再说**
- 跨参考：[[feedback-no-mock-for-external-systems]] — 如果早点用真实容器跑诊断测试，第一次就能发现
