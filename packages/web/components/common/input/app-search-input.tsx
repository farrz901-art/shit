/**
 * 搜索输入框 — Lucide Search 图标 + 受控值 + useDebounce 同步 (2026-06-15)
 * 替 `<div className="relative"><Input ... /></div>` 模板 8+ 处
 * 内部维护 local state + useDebounce 触发 onChange, 外部 value 改变时 useEffect 同步
 */
"use client";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useDebounce } from "react-use";
import { useEffect, useState } from "react";

/** 默认防抖延迟毫秒数 */
const DEFAULT_DEBOUNCE_MS = 300;

/**
 * SearchInput 属性接口 — 受控值、变化回调、占位符及防抖延迟
 * @client-bff
 */
interface SearchInputProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  debounceMs?: number;
}

/**
 * 搜索输入框 — Lucide Search 图标 + 受控值 + useDebounce 同步触发 onChange
 * @param props.value 外部受控值
 * @param props.onChange 值变化回调 (debounce 后触发)
 * @param props.placeholder 占位符
 * @param props.debounceMs 防抖延迟 ms (默认 300)
 * @returns 搜索框 JSX
 */
export const SearchInput = ({
  value,
  onChange,
  placeholder = "搜索...",
  debounceMs = DEFAULT_DEBOUNCE_MS,
}: SearchInputProps) => {
  const [local, setLocal] = useState(value);

  useDebounce(
    () => {
      onChange(local);
    },
    debounceMs,
    [local],
  );

  useEffect(() => {
    setLocal(value);
  }, [value]);

  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        className="pl-10"
        placeholder={placeholder}
        value={local}
        onChange={(event) => setLocal(event.target.value)}
      />
    </div>
  );
};
