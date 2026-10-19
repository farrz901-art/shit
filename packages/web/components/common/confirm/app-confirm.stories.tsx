"use client";
// AppConfirm 交互演示 (2026-06-10)
// 三个 story 用 function component + useState 模拟"打开/关闭"交互
import { AppConfirm } from "./app-confirm";
import { Button } from "@/components/ui/button";
import { useState } from "react";

export const BasicStory = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="destructive" onClick={() => setOpen(true)}>
        删除
      </Button>
      <AppConfirm
        open={open}
        onOpenChange={setOpen}
        title="删除会话"
        description="此操作不可撤销"
        variant="destructive"
        onConfirm={() => alert("已删除")}
      />
    </>
  );
};

export const DefaultStory = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>提交</Button>
      <AppConfirm
        open={open}
        onOpenChange={setOpen}
        title="确认提交"
        description="提交后无法修改"
        onConfirm={() => alert("已提交")}
        onCancel={() => alert("已取消")}
      />
    </>
  );
};

export const CustomTextStory = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="outline" onClick={() => setOpen(true)}>
        发布
      </Button>
      <AppConfirm
        open={open}
        onOpenChange={setOpen}
        title="发布文档"
        description="发布后所有协作者可见"
        confirmText="立即发布"
        cancelText="再想想"
        onConfirm={() => alert("已发布")}
      />
    </>
  );
};
