"use client";
/**
 * 错误边界 (2026-06-15) — 从 components/knowledge/ 升 common/
 * 防止子组件抛错拖垮整站, 任何模块都能包. 零 knowledge 依赖
 * (2026-06-14) shadcn: 原生 <button> → <Button variant="link">
 * 用法: <ErrorBoundary><Page/></ErrorBoundary>
 *      抛错时显示错误信息 + 重试按钮
 */
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Component, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

/** 错误边界内部状态 — 记录捕获的 Error 对象 */
interface State {
  error: Error | null;
}

/**
 * React 错误边界 Class 组件 — 子树抛错时显示降级 UI + 重试按钮
 * 触发 reset: 子组件状态变更 (新 key 强制重 mount) 或 setState error: null
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <Card className="border-status-error/40" data-testid="error-boundary">
          <CardHeader>
            <CardTitle className="text-status-error">出错了</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-sm text-status-error whitespace-pre-wrap">
              {this.state.error.message}
            </pre>
            <Button
              variant="link"
              className="mt-2 h-auto p-0 text-base text-primary underline"
              onClick={() => this.setState({ error: null })}
            >
              重试
            </Button>
          </CardContent>
        </Card>
      );
    }
    return this.props.children;
  }
}
