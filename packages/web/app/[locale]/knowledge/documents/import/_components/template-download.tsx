/**
 * TemplateDownload (2026-06-29)
 * 抽自 documents-import-form.tsx 的模板下载卡 (Excel + JSON 两个按钮)
 * 用项目 ButtonLift + shadcn Button asChild 组合
 */
"use client";
import { ButtonLift } from "@/components/motion/animated";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * TemplateLink - 模板下载链接定义
 * @property label - 按钮显示文本 (已 i18n)
 * @property href - 下载地址
 * @property downloadName - 下载文件名
 * @property testId - 测试 ID
 */
export interface TemplateLink {
  /** 按钮显示文本 (已 i18n) */
  label: string;
  /** 下载地址 (e.g. /templates/qa-template.xlsx) */
  href: string;
  /** 下载文件名 (download 属性) */
  downloadName: string;
  /** 测试 ID */
  testId: string;
}

/** TemplateDownloadProps - 模板下载卡属性 */
export interface TemplateDownloadProps {
  title: string;
  templates: TemplateLink[];
}

/**
 * TemplateDownload - 模板下载卡
 * @param props.title - 卡片标题
 * @param props.templates - 模板链接列表
 * @client-bff
 */
export const TemplateDownload = ({ title, templates }: TemplateDownloadProps) => (
  <Card className="border-border/60">
    <CardHeader>
      <CardTitle className="text-lg">{title}</CardTitle>
    </CardHeader>
    <CardContent className="flex flex-wrap gap-2">
      {templates.map((tpl) => (
        <ButtonLift key={tpl.testId}>
          <Button asChild variant="outline" data-testid={tpl.testId}>
            <a href={tpl.href} download={tpl.downloadName}>
              <Download className="mr-2 h-4 w-4" />
              {tpl.label}
            </a>
          </Button>
        </ButtonLift>
      ))}
    </CardContent>
  </Card>
);
