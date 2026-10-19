# D3 — Error handling 审计 (2026-07-07)

> 扫描范围: `packages/web/lib/api/**`、`packages/web/components/**`、RSC fetch 路径、`packages/web/app/api/**` BFF、`packages/service/src/**`
> 工具: Read / Grep (无网络). 共 10 条 finding.

## 摘要

| ID | 维度 | 严重度 | 置信度 | 标题 |
|---|---|---|---|---|
| ERR-001 | error | high | high | 后端 chat_share/router.py 透传 Dify 原始异常 message 给前端 |
| ERR-002 | error | high | high | 后端 product_decoders/router.py 5xx 路径泄漏原始异常 message |
| ERR-003 | error | high | high | 后端 ingest/pre_analysis/router.py + account_settings_router.py 用 `str(e)` 作 HTTPException detail 泄漏内部异常 |
| ERR-004 | error | medium | high | 后端 ingest/pdf_processing/router.py 把完整 traceback 写进 task.error, 前端 GET /api/ingest/tasks 直接暴露 |
| ERR-005 | error | high | high | 前端 BFF /api/chat/messages 把 provider 抛错 message 原样塞进 SSE error 事件 |
| ERR-006 | error | medium | high | 前端 lib/api/system.ts 用 10s AbortController 超时, 其它 25+ 个 fetch 调用零超时保护 |
| ERR-007 | error | medium | medium | 前端 lib/api/ingest.ts presign PUT 到 MinIO 无超时 + 无重试, 网络挂起永久卡住 |
| ERR-008 | error | medium | high | 前端 app/api/auth/anon/route.ts fetch 后端失败时直接抛到 Next.js 默认 500, 无 502 透传 |
| ERR-009 | error | low | high | 后端 storage/object_store.py MinIO impl 10 处 `except Exception` 后用 `isinstance(e, ClientError)` 判断, isinstance 之外的 TypeError 等也会被吞 |
| ERR-010 | error | low | medium | 前端 apiFetch() 4xx/5xx 时无重试, RSC 预取 + 客户端 useQuery 全 retry: false, 用户瞬时网络抖动就 toast 报错 |

---

## ERR-001 — chat_share Dify 异常 detail 直透前端

**dimension**: error
**severity**: high
**confidence**: high
**file**: `packages/service/src/chat_share/router.py`
**line**: 411-413

**description**:
`/api/chat/shares/finalize` 在调用 Dify Files API 失败时, 把 Python 异常对象 `str(e)` 直接拼到 HTTPException 的 `detail` 字段返回给前端. 该 detail 由 FastAPI 直接 JSON 化为响应 body. Dify 5xx 错误体、httpx 库的 timeout/network 错误文本都可能包含 Dify 内部 endpoint、API key 前缀、上游 URL 等敏感上下文, 攻击者拿到 share 链接即可探测.

**evidence**:
```python
404:    except ObjectStoreError as e:
405:        raise HTTPException(status_code=503, detail=str(e)) from e
406:
407:    # 转发 Dify (用 service 走 httpx)
408:    try:
...
411:    except Exception as e:
412:        # Dify 失败: URI 保留, 让前端重试
413:        raise HTTPException(status_code=500, detail=f"Dify 转发失败: {e}") from e
```

**impact**:
- 高: 用户 (含未登录 share 访问者) 可看到 Dify 内部异常消息, 包括 API endpoint URL、SSL 错误详情、网络层错误, 有助外部攻击者侦察后端架构
- 中: 与项目 `core/errors.py:60` (unhandled_exc 永远只返 "Internal server error" 不泄 stacktrace) 的全局策略直接冲突
- 同文件 503/500/404 路径三处都犯了同样问题

**fix_sketch**:
把 detail 替换成稳定的 `f"Dify 转发失败 (request_id={rid})"` (rid 走 `current_request_id` contextvar), 完整异常走 `logger.opt(exception=True).error(...)` + `_error_sink_sync` 写 error_logs. 503 (ObjectStore) 同理, 只返 `"对象存储不可用"` + rid.

---

## ERR-002 — product_decoders /decode 5xx 路径泄漏原始异常

**dimension**: error
**severity**: high
**confidence**: high
**file**: `packages/service/src/product_decoders/router.py`
**line**: 65-66

**description**:
`/decode` 端点兜底 `except Exception as e` 把 `str(e)` 直接拼到 500 detail. 解码器读 YAML 配置文件, 异常 message 常包含 yaml 文件绝对路径、字段名、行号 (如 yaml.parser.ParserError: expected '<document start>', but found '<scalar>' in ".../config/siemens.yaml", line 42, column 3). 公开 endpoint 无鉴权, 任何前端用户都能拿到服务器内部配置路径.

**evidence**:
```python
57:async def decode(req: DecodeRequest):
58:    """解码产品订货号"""
59:    try:
60:        result = _decoder.decode(req.model)
61:        result["llm_view"] = _decoder.build_llm_view(result)
62:        return result
63:    except ValueError as e:
64:        raise HTTPException(status_code=400, detail=str(e))
65:    except Exception as e:
66:        raise HTTPException(status_code=500, detail=f"内部错误: {e}")
```

**impact**:
- 高: 无鉴权端点直接暴露项目路径, 攻击者可直接 `/etc/passwd` 探测 + yaml config fuzzing
- ValueError 路径 (line 64) 同样泄漏: 解码器返回的 ValueError 包含输入字符串, 信息泄露低但仍是反模式

**fix_sketch**:
5xx 改 `raise HTTPException(500, detail="内部错误")` + `logger.opt(exception=True).error(...)`; 400 路径若涉及内部 schema 可只返 `"解码失败: {req.model[:50]}"` (截断输入), 完整异常走 logger.

---

## ERR-003 — 6 处路由用 `str(e)` / `f"...{e}"` 作 HTTPException detail

**dimension**: error
**severity**: high
**confidence**: high
**file**: `packages/service/src/auth/account_settings_router.py` 等 6 文件
**line**: 多处

**description**:
扫描发现 6 个 router 文件在 except 后用 `detail=str(e)` 或 `f"...{e}"` 直接把内部异常 message 返给前端. 与 `core/errors.py` 全局 unhandled_exc handler "永远不返 stacktrace 给前端" 的策略冲突, 但这些都通过手动 raise HTTPException 绕过全局 handler (HTTPException 由独立的 StarletteHTTPException handler 接, 见 `core/errors.py:23`, 它**不**做 redact, 直接把 detail 写日志后透传).

**evidence**:
```python
# packages/service/src/auth/account_settings_router.py:173
            raise HTTPException(status_code=404, detail=f"avatar file missing: {e}") from e
# packages/service/src/auth/account_settings_router.py:113
            raise HTTPException(status_code=422, detail=str(e)) from e
# packages/service/src/lookups/admin_router.py:248/309/371/440
        raise HTTPException(status_code=404, detail=str(e)) from e
# packages/service/src/lookups/router.py:96/128
        raise HTTPException(status_code=404, detail=str(e)) from e
# packages/service/src/memory/router.py:217/254
        raise HTTPException(status_code=403, detail=str(e)) from e
```

**impact**:
- 高: `account_settings_router.py:113` 把 password 校验异常 str() 后返 422, 可能含内部 token 校验逻辑文本
- 高: lookups / memory 403/404 路径可能把 ORM Column 名、Pydantic 校验 message 泄漏给前端, 帮助探测权限边界
- 中: PDF router 528 行为见 ERR-004, 是同一反模式的更严重版本

**fix_sketch**:
1) 替换为 `logger.opt(exception=True).warning(...)` + 稳定 detail (例 `f"对象 {resource_id} 不存在"`).
2) 或加 `_scrub_exception_message(e)` 工具: 把 SQL/orm/路径替换成 `***`, 仅保留 type 名 + 用户可见字段.
3) 一次性扫 `grep -rE 'detail=(str\(e\)|f"[^"]*\{e\})' packages/service/src` 找出全部位置统一修.

---

## ERR-004 — PDF router 把完整 traceback 写进 task.error, API 直接暴露

**dimension**: error
**severity**: medium
**confidence**: high
**file**: `packages/service/src/ingest/pdf_processing/router.py`
**line**: 526-528

**description**:
后台 PDF 处理异常时, `repr(traceback.format_exc())` 把完整 traceback (含本地绝对路径 / PyMuPDF 版本号 / mineru 配置) 写入 `tasks.error` 字段, `GET /api/ingest/tasks` 接口直接把这个字段作为 JSON 返回. super_admin 用户看到有助于 debug, 但 traceback 是大字符串 (KB 级), 不是精心设计的错误消息.

**evidence**:
```python
526:        t.state = "failed"
527:        # 走完一遍 process_path, 收集结果
528:        t.error = repr(traceback.format_exc())
529:    finally:
530:        t.finished_at = datetime.now()
531:        _save(t)
```

**impact**:
- 中: super_admin 看到自身信息 (本地路径), 是低风险但违反"error 是给开发者看, API 是给前端展示"分层原则
- 中: traceback 行数随异常深度膨胀, 大 task 列表页 N 个 failed task 累积上百 KB, 拖慢列表查询响应
- 低: PDF router 是 `super_admin` 限定, 不存在公开泄漏

**fix_sketch**:
写 `t.error = f"{type(e).__name__}: {str(e)[:200]}"` 只保留类型 + 截断消息, 完整 traceback 走 `logger.opt(exception=True).error(...)` (异步路径已有 lifespan logger 接管).

---

## ERR-005 — chat BFF SSE 错误事件把 provider 异常 message 原样转给前端

**dimension**: error
**severity**: high
**confidence**: high
**file**: `packages/web/app/api/chat/messages/route.ts`
**line**: 155-160

**description**:
`provider.sendMessage` (Dify / OpenAI 包装) 抛错时, route 把 `(error as Error).message` 放进 SSE `error` 事件, 前端 UI 直接展示. provider message 常含 Dify upstream 5xx body、httpx timeout URL、API endpoint 路径 (`post "https://api.dify.ai/v1/chat-messages": 502 Bad Gateway`). 此外 `(error as Error).message` 在 non-Error throw (string / number) 下是 `undefined`, 客户端会展示空字符串.

**evidence**:
```ts
154:      } catch (error) {
155:        controller.enqueue({
156:          code: "upstream_error",
157:          message: (error as Error).message,
158:          type: "error",
159:        } as ChatEvent);
160:      } finally {
161:        controller.close();
162:      }
```

**impact**:
- 高: 公开 chat endpoint (chat-public-token 鉴权), 任何带 token 的前端用户能看到 LLM provider 内部异常消息
- 中: `(error as Error).message` 类型不安全, non-Error throw 时 `.message` 为 `undefined`, JSON 序列化成 null, 前端显示空

**fix_sketch**:
1) `message: getErrorMessage(error)` (项目已有 util, 兼容 string/Error/未知).
2) 加 mapping: Dify 5xx → `"智能体服务暂时不可用, 请稍后再试"`; timeout → `"请求超时"`; HTTPStatusError → 限定 4 类友好文案.
3) 真实异常 message + stack 走 `log.error(...)` (server-only, 不走 SSE).

---

## ERR-006 — 前端 25+ 个 fetch 调用零超时保护, 仅 system.ts 有 10s AbortController

**dimension**: error
**severity**: medium
**confidence**: high
**file**: `packages/web/lib/api/`
**line**: 多文件

**description**:
`lib/api/system.ts:34` 是唯一带 `AbortSignal.timeout(10_000)` 的 api 调用. 其它 25+ 调用 (`chat.ts:97`, `ingest.ts:169`, `knowledge.ts:448`, `pre-analysis.ts:173/233/251`, `config.ts:43/179`, server `evaluate.ts:16`, `memory-integration.ts:66/97/126`) 全部裸 `await fetch()`, 无超时. 后端 8000 端口挂起 (PG 慢查询 / 死锁) 时, 前端请求会无限挂, 浏览器只在 ~5 分钟 (Chrome default) 后才断开, UI 卡死. RSC 端 (`rscGet`) 同问题, 加重启 dev server 才恢复.

**evidence**:
```ts
// packages/web/lib/api/system.ts:17-34 (唯一带 timeout)
17:const DEFAULT_TIMEOUT_MS = 10_000;
...
33:export const listDatasets = () => {
34:  return apiFetch("/api/datasets", { signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS) });
35:};

// packages/web/lib/api/chat.ts:97 (无超时)
97:  const putResp = await fetch(put_url, { ... });

// packages/web/lib/api/pre-analysis.ts:173 (无超时, 上传 PDF)
173:  const resp = await fetch("/api/pre-analysis/upload", { ... });

// packages/web/lib/api/ingest.ts:169 (无超时, PUT 到 MinIO)
169:    const putResp = await fetch(up.put_url, { ... });
```

**impact**:
- 中: 用户上传 PDF / 大文件挂起无提示, 浏览器持续占内存
- 中: RSC prefetch 阻塞渲染 (Next.js 等到上游 abort 或超时), 影响 LCP
- 低: chat Dify 流 (`sendMessage`) 走 `req.signal` 透传客户端 abort, 不受此影响

**fix_sketch**:
1) `lib/api/config.ts` 的 `apiFetch` / `apiProxy` 加默认 timeout 参数 (`defaultTimeoutMs?: number = 30_000`), 调用方可覆盖.
2) 给 MinIO PUT / 文件上传场景加更激进超时 (e.g. 120s).
3) 一次性加 README 段说明: 所有外部 IO 都必须显式传 signal 或走封装默认.

---

## ERR-007 — ingest presign PUT 到 MinIO 无超时 + 无重试 + 无 abort signal

**dimension**: error
**severity**: medium
**confidence**: high
**file**: `packages/web/lib/api/ingest.ts`
**line**: 163-177

**description**:
`uploadViaPresign` 走 presign 拿到 MinIO PUT URL 后, 用裸 `fetch(put_url, ...)` 串行上传每个文件. 缺超时 + 无重试 + 无 abort. MinIO 临时不可达时浏览器 fetch 无限挂, 不支持 cancel (用户点击"取消"按钮无效果). 大文件 (200MB) 上传失败重试代价高, 现状只能整批重传.

**evidence**:
```ts
163:  for (let idx = 0; idx < files.length; idx++) {
164:    const file = files[idx];
165:    const up = presign.uploads[idx];
166:    if (!up.put_url) {
167:      throw new Error(`presign 未返 PUT URL for ${up.name}`);
168:    }
169:    const putResp = await fetch(up.put_url, {
170:      body: file,
171:      headers: { [HEADER_CONTENT_TYPE]: up.mime },
172:      method: "PUT",
173:    });
174:    if (!putResp.ok) {
175:      throw new Error(`PUT MinIO 失败: ${putResp.status}`);
176:    }
177:  }
```

**impact**:
- 中: 用户上传 5 个 100MB PDF, 第 3 个 MinIO 503 → 前面 2 个已上传 (Orphan), 后端 finalize 时 task 处于半残状态. 后端 cleanup 30d GC 才能回收
- 中: 缺 AbortController 无法响应用户取消, 浏览器内存 + 网络持续占用
- 低: 仅 1 处缺重试, 单文件 PUT 失败成本不算高

**fix_sketch**:
1) 加 `AbortController` 由调用方注入 (caller 控制取消), 默认 5min 超时.
2) 单文件 PUT 失败加 1 次重试 (同 presign URL, idempotent PUT 安全).
3) `finalize` 前若所有文件 PUT 全失败, 调后端 `/api/ingest/upload/abort` 释放 task_id, 防 orphan 累积.

---

## ERR-008 — BFF /api/auth/anon fetch 后端失败时直接抛到 Next.js 默认 500 handler

**dimension**: error
**severity**: medium
**confidence**: high
**file**: `packages/web/app/api/auth/anon/route.ts`
**line**: 22-28

**description**:
`/api/auth/anon` BFF 直接 `await fetch(API_BASE + '/api/auth/anon')`, 无 try/catch. 后端 8000 挂掉 / ECONNREFUSED 时 fetch 抛出 NetworkError, 异常冒到 Next.js runtime 产生 HTML 500 页 (不是 JSON 502), 前端 `AuthBootstrap` 拿到非 JSON 响应 `await res.json()` 直接 SyntaxError. 期望 BFF 应该走 502 JSON + 结构化 detail, 跟 catch-all proxy (`app/api/[...path]/route.ts:121 proxyErrorResponse`) 行为一致.

**evidence**:
```ts
22:export const POST = async (_req: NextRequest) => {
23:  const upstream = await fetch(`${API_BASE}/api/auth/anon`, {
24:    cache: "no-store",
25:    method: "POST",
26:  });
27:  return proxyAuthResponse(upstream);
28:};
```

**impact**:
- 中: 后端挂掉时浏览器 anon bootstrap 永远失败, 用户看到 "Unexpected token <" 而不是 "服务暂不可用"
- 中: 该 BFF 是其他 `/api/*` 401 链的入口, 一旦挂了整个 RAG 站点对匿名用户不可用
- 低: catch-all 路由有同样问题但已用 `proxyErrorResponse` 修了, 这条 route 是漏网之鱼

**fix_sketch**:
加 `try { upstream = await fetch(...) } catch (error) { return Response.json({ detail: `upstream 不可达: ${(error as Error).message}` }, { status: 502 }) }`. 跟 `app/api/[...path]/route.ts:121` 共享 `proxyErrorResponse` util.

---

## ERR-009 — object_store.py MinIO 10 处 `except Exception` 后用 isinstance 守卫, 静默吞 TypeError / ValueError

**dimension**: error
**severity**: low
**confidence**: high
**file**: `packages/service/src/storage/object_store.py`
**line**: 325-430

**description**:
MinIO impl 每个 CRUD 方法都 `except Exception as e`, 然后用 `isinstance(e, (ClientError, requests.RequestException, OSError))` 判断是否转 ObjectStoreError. 其它异常类型 (TypeError, AttributeError, KeyError, ValueError) 直接 `raise` 透传, 但因为外面是 `except Exception`, 异常的 traceback 被这里抓住后才 raise, 调试时日志会看到两层 except 混淆. 更糟: `is_not_found` 分支 (line 376-384) 当 e 不是 ClientError 时回退到 `str(e)` 子串匹配 `"NoSuchKey" in str(e)`, 但 KeyError/TypeError 的 str() 完全可能包含这个子串 (哈希/字典键), 误判为 ObjectNotFound.

**evidence**:
```python
369:    def get_bytes(self, uri: str) -> bytes:
370:        key = self._resolve(uri)
371:        try:
372:            resp = self._client.get_object(Bucket=self._bucket, Key=key)
373:            return resp["Body"].read()
374:        except Exception as e:
375:            # 优先用 ClientError.response["Error"]["Code"] 结构化检查, fallback 到 str 子串 (防御性)
376:            is_not_found = False
377:            if ClientError is not None and isinstance(e, ClientError):
378:                code = e.response.get("Error", {}).get("Code", "")
379:                if code in ("NoSuchKey", "NoSuchVersion", "404"):
380:                    is_not_found = True
381:            elif "NoSuchKey" in str(e) or "404" in str(e):
382:                is_not_found = True
```

**impact**:
- 低: 实际生产 boto3 抛错类型明确, 误判概率小; 但单测覆盖不到的小版本差异可能误判, 把真 bug 包装成 ObjectNotFound (404) 让上层业务重试
- 低: 这是 storage ABC 层的防御性兜底, 行为没问题但代码读起来不直观

**fix_sketch**:
1) 收紧 except: `except (ClientError, requests.RequestException, OSError, KeyError) as e`, 直接排除 TypeError/AttributeError 这类不该被这里吞的异常.
2) `is_not_found` 严格用 ClientError 结构化路径, 删 fallback str(e) 子串匹配.
3) 加注释解释 `botocore ClientError.response` 形状, 让下一个读者不用猜.

---

## ERR-010 — RSC prefetch + 客户端 useQuery 都 `retry: false`, 瞬时网络抖动直接 toast 报错

**dimension**: error
**severity**: low
**confidence**: medium
**file**: `packages/web/lib/api/rsc-queries.ts` + `packages/web/lib/api/query-client.ts`
**line**: 24 / 23

**description**:
两处 queryClient 配置都明确 `retry: false`, 设计意图是"避免静默重试, 失败让上层弹错". 但 0 重试意味着用户刷新页面时若瞬时网络抖 (DNS 慢解析 / 后端冷启动 / 移动网络切换), 100% 触发 toast. 生产环境实际验证会大量假报错. TanStack Query 默认 3 次指数退避 retry 是更稳健的默认, 至少 1-2 次重试覆盖"瞬时"场景.

**evidence**:
```ts
// packages/web/lib/api/rsc-queries.ts:24
22:    new QueryClient({
23:      defaultOptions: {
24:        queries: { gcTime: 0, retry: false, staleTime: Infinity },
25:      },
26:    }),
// packages/web/lib/api/query-client.ts:23
20:export const createBrowserQueryClient = (): QueryClient =>
21:  new QueryClient({
22:    defaultOptions: {
23:      queries: { gcTime: 0, retry: false, staleTime: Infinity },
24:    },
```

**impact**:
- 低: 用户体验差但无数据丢失, 用户点 toast 重试 / 刷新页面就好
- 低: 不影响事务安全 (GET 幂等)

**fix_sketch**:
改 `retry: 2` + `retryDelay: attempt => Math.min(1000 * 2 ** attempt, 5000)` (1s → 2s → 4s 上限). mutation (POST/PATCH/DELETE) 保持 retry: false 防重放. RSC prefetch 单独判断: 第一次失败时 return 而非 retry, 留给 client useQuery 接管.

---

## 反模式观察 (非 finding)

以下模式普遍存在但不算严重问题, 仅作记录, 不进 finding 表:

1. **后端 `except Exception` 在 lifespan 启动期常见** (`core/lifespan.py` 7 处): 都走 `logger.warning(... 跳过 (降级模式))`, 设计目的是"启动期 seed 失败不阻塞服务", 策略一致, OK.

2. **前端 `parseErrorDetail` / `parseResponseBody` 用 `try {} catch {}` 静默吞 JSON 解析错**: 这是合理的 (失败 fallback 到原文), 见 `lib/api/config.ts:127-155`.

3. **前端 ErrorBoundary + global-error + query-client QueryCache.onError 三层兜底**: 设计完整, RSC throw 由 `app/[locale]/error.tsx` 兜住, useQuery 失败由 QueryCache 弹 toast, 跟 `feedback-rsc-throw-must-not-crash-page` 经验一致.

4. **PII scrubber (`core/logging.py:_scrub`) 走 case-insensitive 黑名单**: 18 字段自动 `***REDACTED***`, 但 `_pg_sink_app` 只对 `context` 列 scrub, `message` 列 (logger format string) 不 scrub. 如果业务代码写 `logger.info("登录用户 token={}", token)` 会被原样落库. 现状下未发现 PII 直接进 message 的代码, 但缺 guard.

5. **chat BFF `/api/chat/messages` 限流 `checkAndIncrement` 走 sync in-memory**: 后端重启后限流计数清零, 攻击窗口期理论上可绕过, 但 `core/rate_limiter.py` 已加 Redis token-bucket 备份 (待 SLA 验证).