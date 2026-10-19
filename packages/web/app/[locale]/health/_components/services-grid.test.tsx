// ServicesGrid 测试 (2026-06-17 加 MinIO 卡片)
// 断言: 5 个 service 卡片, MinIO 卡片在 minio backend 时显示 latency + bucket/endpoint,
//        在 local backend 时显示 "local" + 跳过提示.
import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithIntl as render } from "@/test-utils/render-with-intl";
import type { CheckResult } from "@/lib/api/health";
import { IntlWrapper } from "@/lib/test-utils/intl-wrapper";
import { ServicesGrid } from "./services-grid";
import { SIX } from "@/const";

const okCheck = (overrides: Partial<CheckResult> = {}): CheckResult => ({
  error: null,
  extra: {},
  latency_ms: 0,
  status: "ok",
  ...overrides,
});

describe("ServicesGrid", () => {
  it("minio backend ok 时: 渲染 MinIO 卡片, 显示 latency + bucket@endpoint", () => {
    render(
      <IntlWrapper locale="zh">
        <ServicesGrid
          python={okCheck({ extra: { uptime_s: 100, version: "0.1.0" } })}
          dify={okCheck({ latency_ms: 120 })}
          neo4j={okCheck({ latency_ms: 45 })}
          pgvector={okCheck({ latency_ms: 30 })}
          minio={okCheck({
            extra: { backend: "minio", bucket: "rag-ingest", endpoint: "http://minio:9000" },
            latency_ms: 18,
          })}
          redis={okCheck({ latency_ms: 2 })}
          uptimeS={100}
          pyVersion="0.1.0"
        />
      </IntlWrapper>,
    );

    // 6 张卡片都渲染
    const sections = screen.getAllByTestId("health-section");
    expect(sections).toHaveLength(SIX);

    // MinIO 卡片存在 + 显示 title
    const minioCard = sections.find((el) => el.getAttribute("data-section-title") === "MinIO");
    expect(minioCard, "MinIO 卡片应存在").toBeDefined();

    // Primary metric = latency (18ms → toFixed(0) = "18")
    expect(minioCard).toHaveTextContent("18");

    // Secondary metric = "rag-ingest@http://minio:9000"
    expect(minioCard).toHaveTextContent("rag-ingest");
    expect(minioCard).toHaveTextContent("http://minio:9000");
  });

  it("local backend (skipped) 时: MinIO 卡片显示 'local' + 未启用提示", () => {
    render(
      <IntlWrapper locale="zh">
        <ServicesGrid
          python={okCheck({ extra: { uptime_s: 100, version: "0.1.0" } })}
          dify={okCheck({ latency_ms: 120 })}
          neo4j={okCheck({ latency_ms: 45 })}
          pgvector={okCheck({ latency_ms: 30 })}
          minio={okCheck({
            extra: { backend: "local", skipped: true },
            latency_ms: 0,
          })}
          redis={okCheck({ latency_ms: 2 })}
          uptimeS={100}
          pyVersion="0.1.0"
        />
      </IntlWrapper>,
    );

    const minioCard = screen
      .getAllByTestId("health-section")
      .find((el) => el.getAttribute("data-section-title") === "MinIO");
    expect(minioCard, "MinIO 卡片应存在 (即使 local backend)").toBeDefined();

    // 显示 backend = "local"
    expect(minioCard).toHaveTextContent("local");
    // 显示 skipped / 未启用 提示
    expect(minioCard).toHaveTextContent(/skipped|未启用/i);
  });

  it("minio backend 错误时: 卡片 status badge 显示 error", () => {
    render(
      <IntlWrapper locale="zh">
        <ServicesGrid
          python={okCheck({ extra: { uptime_s: 100, version: "0.1.0" } })}
          dify={okCheck({ latency_ms: 120 })}
          neo4j={okCheck({ latency_ms: 45 })}
          pgvector={okCheck({ latency_ms: 30 })}
          minio={{
            error: "connection refused",
            extra: { backend: "minio", bucket: "rag-ingest" },
            latency_ms: null,
            status: "error",
          }}
          redis={okCheck({ latency_ms: 2 })}
          uptimeS={100}
          pyVersion="0.1.0"
        />
      </IntlWrapper>,
    );

    const minioCard = screen
      .getAllByTestId("health-section")
      .find((el) => el.getAttribute("data-section-title") === "MinIO");
    expect(minioCard).toBeDefined();
    expect(minioCard).toHaveTextContent("error");
  });

  it("redis ok 时: 渲染 Redis 卡片, 显示延迟和状态", () => {
    render(
      <IntlWrapper locale="zh">
        <ServicesGrid
          python={okCheck({ extra: { uptime_s: 100, version: "0.1.0" } })}
          dify={okCheck({ latency_ms: 120 })}
          neo4j={okCheck({ latency_ms: 45 })}
          pgvector={okCheck({ latency_ms: 30 })}
          minio={{
            error: null,
            extra: { backend: "local", skipped: true },
            latency_ms: 0,
            status: "ok",
          }}
          redis={okCheck({ latency_ms: 2 })}
          uptimeS={100}
          pyVersion="0.1.0"
        />
      </IntlWrapper>,
    );

    const redisCard = screen
      .getAllByTestId("health-section")
      .find((el) => el.getAttribute("data-section-title") === "Redis 缓存");
    expect(redisCard, "Redis 卡片应存在").toBeDefined();
    expect(redisCard).toHaveTextContent("2");
  });

  it("redis error 时: 卡片状态 badge 显示 error", () => {
    render(
      <IntlWrapper locale="zh">
        <ServicesGrid
          python={okCheck({ extra: { uptime_s: 100, version: "0.1.0" } })}
          dify={okCheck({ latency_ms: 120 })}
          neo4j={okCheck({ latency_ms: 45 })}
          pgvector={okCheck({ latency_ms: 30 })}
          minio={{
            error: null,
            extra: { backend: "local", skipped: true },
            latency_ms: 0,
            status: "ok",
          }}
          redis={{
            error: "connection refused",
            extra: {},
            latency_ms: null,
            status: "error",
          }}
          uptimeS={100}
          pyVersion="0.1.0"
        />
      </IntlWrapper>,
    );

    const redisCard = screen
      .getAllByTestId("health-section")
      .find((el) => el.getAttribute("data-section-title") === "Redis 缓存");
    expect(redisCard).toBeDefined();
    expect(redisCard).toHaveTextContent("error");
  });
});
