import { FieldDef, KnowledgeSchema, NodeDef } from "./schema-types";
import { describe, expect, it } from "vitest";

describe("schema-types", () => {
  it("parses valid field def", () => {
    const fieldDef = FieldDef.parse({
      key: "model",
      label: "型号",
      required: true,
      type: "string",
    });
    expect(fieldDef.type).toBe("string");
  });

  it("rejects unknown field type", () => {
    expect(() => FieldDef.parse({ key: "x", label: "X", type: "weird" })).toThrow();
  });

  it("parses full schema", () => {
    const schema = KnowledgeSchema.parse({
      nodes: [{ fields: [{ key: "model", label: "型号", type: "string" }], name: "Product" }],
      relations: [{ cardinality: "many_to_one", from: "Product", name: "REL", to: "Product" }],
    });
    const [firstNode] = schema.nodes;
    expect(firstNode.name).toBe("Product");
  });

  it("NodeDef defaults fields to empty array", () => {
    const nodeDef = NodeDef.parse({ name: "X" });
    expect(nodeDef.fields).toEqual([]);
  });
});
