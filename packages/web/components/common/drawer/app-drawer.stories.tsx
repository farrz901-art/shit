"use client";
import { AppDrawer } from "./app-drawer";
import { Button } from "@/components/ui/button";
import { useState } from "react";

export const RightDrawerStory = () => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>打开右侧抽屉</Button>
      <AppDrawer open={open} onOpenChange={setOpen} title="任务详情" footer={<Button>完成</Button>}>
        <p>抽屉内容</p>
      </AppDrawer>
    </>
  );
};
