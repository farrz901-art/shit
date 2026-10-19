"use client";
/**
 * Schema domain 选择器 — 切换知识图谱 schema domain, 写到 zustand store
 * 用 StandaloneQueryProvider 自包 QueryClient 单例
 * @param props.onChange domain 变更回调
 * @returns JSX 元素
 * @client-bff
 */
// 模式: useSWR → useQuery (Task 28-prep, 2026-06-12 redesign) — 跟 HealthDot / DatasetSwitcher 同型:
//   - 挂在 root Header (不在 B 档 QC provider 下), 走 <StandaloneQueryProvider> 单例 QC.
//   - 后端 /api/kg/schemas 返回裸数组 [{ domain, file }] (直连 FastAPI, 无 BFF 包装).
// (2026-06-28 P3) 改用 <StandaloneQueryProvider> 替内联 useState QueryClient 工厂.
import { useQuery } from "@tanstack/react-query";
import { AppSelect } from "@/components/common/input/app-select";
import { StandaloneQueryProvider } from "@/components/common/providers";
import { fetchSchemas } from "@/lib/api/knowledge";
import { useAppStore } from "@/lib/store/app-store";

/**
 * Schema 信息
 * @property domain 领域名称
 * @property file 文件路径
 */
interface SchemaInfo {
  domain: string;
  file: string;
}

/** Schema 查询 key */
const QK_SCHEMAS = ["rag", "knowledge", "schemas"] as const;

/**
 * Schema domain 选择器内部组件 (StandaloneQueryProvider 子节点)
 * @param props.onChange domain 变更回调
 * @returns JSX 元素
 */
const Switcher = ({ onChange }: { onChange?: (domain: string) => void }) => {
  // 直连 FastAPI /api/kg/schemas
  const { data } = useQuery({
    queryFn: () => fetchSchemas(),
    queryKey: QK_SCHEMAS,
  });
  const domain = useAppStore((state) => state.domain);
  const setDomain = useAppStore((state) => state.setDomain);

  const onValueChange = (next: string) => {
    setDomain(next);
    onChange?.(next);
  };

  // 后端 /api/kg/schemas 返回裸数组 [{ domain, file }]; fetchSchemas 类型标错 (历史 type cast),
  // 实际拿 { schemas: { name: string }[] }, 运行时 r.json() 实际是裸数组, 故做 Array.isArray 兜底
  let schemas: SchemaInfo[] = [];
  // eslint-disable-next-line unicorn/prefer-ternary -- 遵守 no-ternary 规则, if/else 更清晰
  if (Array.isArray(data)) {
    schemas = data as unknown as SchemaInfo[];
  } else {
    schemas = (data as unknown as { schemas?: SchemaInfo[] })?.schemas ?? [];
  }

  return (
    <AppSelect
      options={schemas.map((schema) => ({ label: schema.domain, value: schema.domain }))}
      value={domain}
      onChange={onValueChange}
      placeholder="选择 domain"
      className="w-40"
      dataTestid="domain-switcher"
    />
  );
};

/** domain-switcher @client-bff */
export const DomainSwitcher = ({ onChange }: { onChange?: (domain: string) => void }) => (
  <StandaloneQueryProvider>
    <Switcher onChange={onChange} />
  </StandaloneQueryProvider>
);
