"use client";
// AppDialog 交互演示 (2026-06-10)
// 三个 story 用 function component + useState 模拟"打开/关闭"交互
import { useState } from "react";
import { AppDialog } from "./app-dialog";
import { Button } from "@/components/ui/button";

export const BasicStory = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>打开弹框</Button>
      <AppDialog open={open} onOpenChange={setOpen} title="基础弹框" description="这是一个描述">
        <p>弹框内容</p>
      </AppDialog>
    </>
  );
};

export const WithFooterStory = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>打开弹框</Button>
      <AppDialog
        open={open}
        onOpenChange={setOpen}
        title="确认操作"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button>保存</Button>
          </>
        }
      >
        <p>表单内容</p>
      </AppDialog>
    </>
  );
};

export const MaxWidthStory = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>打开大弹框</Button>
      <AppDialog open={open} onOpenChange={setOpen} title="大弹框" maxWidth="3xl">
        <p>3xl 宽度</p>
      </AppDialog>
    </>
  );
};
