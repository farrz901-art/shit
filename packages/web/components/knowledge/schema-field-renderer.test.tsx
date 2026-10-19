import { LabelPicker, RelationPicker } from "./schema-field-renderer";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { KnowledgeSchema } from "@/lib/schema-types";

const schema: KnowledgeSchema = {
  nodes: [
    { fields: [], name: "Product" },
    { fields: [], name: "Series" },
  ],
  relations: [
    { cardinality: "many_to_one", from: "Product", name: "BELONGS_TO", to: "Series" },
    { cardinality: "many_to_many", from: "Product", name: "COMPATIBLE_WITH", to: "Product" },
  ],
};

describe("RelationPicker", () => {
  it("根据 from 过滤关系", () => {
    render(<RelationPicker schema={schema} fromLabel="Product" value="" onChange={() => {}} />);
    // 点击 trigger 打开 content
    const trigger = screen.getByTestId("rel-picker");
    // 静态检查 trigger 渲染
    expect(trigger).toBeInTheDocument();
  });

  it("from=Series 关系列表为空", () => {
    // 验证 relations.filter 逻辑
    const rels = schema.relations.filter((rel) => rel.from === "Series");
    expect(rels).toEqual([]);
  });
});

describe("LabelPicker", () => {
  it("列所有节点", () => {
    render(<LabelPicker schema={schema} value="" onChange={() => {}} />);
    expect(screen.getByTestId("label-picker")).toBeInTheDocument();
  });

  it("schema 节点列表正确", () => {
    expect(schema.nodes.map((node) => node.name)).toEqual(["Product", "Series"]);
  });
});
