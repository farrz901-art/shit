"use client";
/**
 * Schema 浏览器 — 弹框展示知识图谱 yaml 节点/关系
 * @param props.open 弹框展开状态
 * @param props.onOpenChange 展开状态回调
 * @returns JSX 元素
 * @client-bff
 */
//   Trigger 按钮由调用方 (graph/page.tsx) 在 actions 插槽里渲染
// (2026-06-14) 改走 apiFetch() 直接给路径
import { AppDialog } from "@/components/common/dialog/app-dialog";
import { fetchSchema } from "@/lib/api/knowledge";
import { useEffect, useState } from "react";
import type { KnowledgeSchema } from "@/lib/schema-types";

/**
 * SchemaBrowser 组件属性
 * @param props.open 弹框展开状态
 * @param props.onOpenChange 展开状态回调
 * @client-bff
 */
export interface SchemaBrowserProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * SchemaBrowser — Schema 浏览器组件
 * 弹框展示知识图谱 yaml 节点/关系
 * @param props.open - 弹框展开状态
 * @param props.onOpenChange - 展开状态回调
 * @returns JSX 元素
 * @client-bff
 */
export const SchemaBrowser = ({ open, onOpenChange }: SchemaBrowserProps) => {
  const [schema, setSchema] = useState<KnowledgeSchema | null>(null);

  useEffect(() => {
    if (open && !schema) {
      // 直连 FastAPI /api/knowledge/schema (默认 domain)
      fetchSchema("motor")
        .then(setSchema)
        .catch(() => undefined);
    }
  }, [open, schema]);

  return (
    <AppDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Schema 浏览器"
      maxWidth="2xl"
      className="max-h-[80vh]"
    >
      {!schema && <p className="text-base">加载中…</p>}
      {schema && (
        <div className="space-y-4 text-base">
          <section>
            <h3 className="font-semibold">节点 ({schema.nodes.length})</h3>
            {schema.nodes.map((node) => (
              <div key={node.name} className="mt-2 rounded border p-2">
                <div className="font-medium">{node.name}</div>
                <ul className="mt-1 list-disc pl-5 text-sm text-muted-foreground">
                  {node.fields.map((field) => {
                    let requiredMark = "";
                    if (field.required) {
                      requiredMark = " *";
                    }
                    return (
                      <li key={field.key}>
                        {field.label} ({field.type}){requiredMark}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </section>
          <section>
            <h3 className="font-semibold">关系 ({schema.relations.length})</h3>
            {schema.relations.map((rel) => (
              <div key={rel.name} className="mt-1 text-sm">
                {rel.from} -[{rel.name}]→ {rel.to} ({rel.cardinality})
              </div>
            ))}
          </section>
        </div>
      )}
    </AppDialog>
  );
};
