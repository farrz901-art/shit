"use client";
/**
 * 长按录音组件 — MediaRecorder API, 按住开始/松开结束
 * 兼容性: 检测 MediaRecorder.isTypeSupported, 不支持则降级提示
 * @param props.onRecorded 录音完成回调, 拿到 Blob 和文件名
 * @returns JSX 元素
 * @client-bff
 */
//
// 用法: 按住麦克风按钮 → start; 松开 → stop + onRecorded(blob, fileName)
// 兼容性: 检测 MediaRecorder.isTypeSupported, 不支持 → 降级提示
// 权限: 浏览器拒绝麦克风权限 → toast 错误
//
// 注: iOS Safari webm/opus 不支持, 显示提示 (YAGNI 不做 iOS 录音)
import { Mic, Square } from "lucide-react";
import { useRef, useState } from "react";
import { useInterval } from "react-use";
import { Button } from "@/components/ui/button";
import { MS_PER_SECOND } from "@/const";
import { cn } from "@/lib/utils";
import { nowMs } from "@/lib/date";
import { toast } from "sonner";
import { useTranslations } from "next-intl";

/**
 * 优先使用的录音 MIME 类型 (按浏览器兼容性排序)
 * @shared
 */
const PREFERRED_MIMES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
/** 计时器更新间隔 (ms) @shared */
const TIMER_INTERVAL_MS = 250;

// Magic number constants (替代字面量 0, 避免 no-magic-numbers 警告)
/** 录音时长初始值 @shared */
const DURATION_START = 0;
/** 最小有效数据块大小 @shared */
const MIN_DATA_SIZE = 0;
/** 时长重置值 @shared */
const DURATION_RESET = 0;

/**
 * 检测浏览器支持的录音格式
 * @returns 支持的 MIME 类型, 无支持时返回 undefined
 * @client-bff
 */
const pickSupportedMime = (): string | undefined => {
  if (typeof MediaRecorder === "undefined") {
    return undefined;
  }
  return PREFERRED_MIMES.find((mime) => MediaRecorder.isTypeSupported(mime));
};

/**
 * 根据 MIME 类型获取录音文件扩展名
 * @param mimeType MIME 类型
 * @returns 文件扩展名 (m4a / webm)
 * @shared
 */
const getFileExtension = (mimeType: string): string => {
  if (mimeType.includes("mp4")) {
    return "m4a";
  }
  return "webm";
};

/**
 * 停止 MediaStream 所有轨道 (释放麦克风)
 * @param stream 媒体流
 * @client-bff
 */
const stopAllTracks = (stream: MediaStream): void => {
  for (const track of stream.getTracks()) {
    track.stop();
  }
};

/**
 * 录音组件属性接口
 * @property onRecorded 录音完成回调, 拿到 Blob 和默认文件名 (timestamp.webm)
 * @client-bff
 */
export interface VoiceRecorderProps {
  onRecorded: (blob: Blob, fileName: string) => void;
}

/**
 * 创建 MediaRecorder 并获取麦克风流
 * @param mimeType 录音格式
 * @returns recorder + stream 对象
 * @client-bff
 */
const setupRecorder = async (
  mimeType: string,
): Promise<{ recorder: MediaRecorder; stream: MediaStream }> => {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const recorder = new MediaRecorder(stream, { mimeType });
  return { recorder, stream };
};

/**
 * 录音逻辑 hook — 管理 MediaRecorder 生命周期 + 计时器
 * @param onRecorded 录音完成回调
 * @returns 录音状态 / 时长 / start / stop
 * @client-bff
 */
const useVoiceRecorder = (onRecorded: VoiceRecorderProps["onRecorded"]) => {
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(DURATION_START);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(DURATION_RESET);
  const mimeType = pickSupportedMime();

  // react-use useInterval 替 setInterval + cleanup useEffect 模板.
  // Delay=null 时 useInterval 内部 clearInterval, 录音停止后自动停止轮询.
  useInterval(
    () => {
      setDuration(Math.floor((nowMs() - startedAtRef.current) / MS_PER_SECOND));
    },
    isRecording ? TIMER_INTERVAL_MS : null,
  );

  /**
   * 实际启动录制流程 (setup + 事件绑定 + 开始录制)
   * @param supportedMime 浏览器支持的 MIME 类型
   * @client-bff
   */
  const runRecorder = async (supportedMime: string): Promise<void> => {
    const { recorder, stream } = await setupRecorder(supportedMime);
    recorderRef.current = recorder;
    chunksRef.current = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > MIN_DATA_SIZE) {
        chunksRef.current.push(event.data);
      }
    };
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: supportedMime });
      const fileName = `recording-${nowMs()}.${getFileExtension(supportedMime)}`;
      onRecorded(blob, fileName);
      // 释放麦克风
      stopAllTracks(stream);
      setIsRecording(false);
      setDuration(DURATION_RESET);
      // isRecording=false → useInterval delay 变 null → 自动 clearInterval, 无需手动清理
    };
    recorder.start();
    setIsRecording(true);
    startedAtRef.current = nowMs();
  };

  /**
   * 开始录音 (检测兼容性 + 请求麦克风权限)
   * @client-bff
   */
  const start = async (): Promise<void> => {
    if (!mimeType) {
      toast.error("录音功能仅支持 Chrome / Edge (MediaRecorder 不可用)");
      return;
    }
    try {
      await runRecorder(mimeType);
    } catch (error) {
      toast.error(`无法访问麦克风: ${(error as Error).message}`);
    }
  };

  return {
    duration,
    isRecording,
    start,
    stop: (): void => {
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
      }
    },
  };
};

/**
 * 长按录音组件 — MediaRecorder API, 按住开始/松开结束
 * @param props.onRecorded 录音完成回调 (Blob + 文件名)
 * @returns JSX 元素
 * @client-bff
 */
export const VoiceRecorder = ({ onRecorded }: VoiceRecorderProps) => {
  const translation = useTranslations();
  const { duration, isRecording, start, stop } = useVoiceRecorder(onRecorded);

  /**
   * 长按开始录音 (pointer down 事件)
   * @param event 指针事件
   * @client-bff
   */
  const onPointerDown = (event: React.PointerEvent) => {
    event.preventDefault();
    void start();
  };

  const label = isRecording ? `${duration}s` : translation("语音");
  const buttonVariant: "destructive" | "outline" = isRecording ? "destructive" : "outline";
  const buttonLabel = isRecording ? translation("录音中…") : translation("语音");

  /**
   * 渲染录音图标 (录音中: 停止方块 / 空闲: 麦克风)
   * @returns JSX 元素
   * @client-bff
   */
  const renderIcon = () => {
    if (isRecording) {
      return <Square className="h-4 w-4 mr-1 fill-current" />;
    }
    return <Mic className="h-4 w-4 mr-1" />;
  };

  /**
   * 渲染录音中状态提示
   * @returns JSX 元素
   * @client-bff
   */
  const renderStatus = () => (
    <span
      className={cn("text-xs text-status-error animate-pulse")}
      data-testid="voice-recorder-status"
    >
      {translation("录音中…")}
    </span>
  );

  return (
    <div className="flex items-center gap-2" data-testid="voice-recorder">
      <Button
        type="button"
        variant={buttonVariant}
        size="sm"
        // Pointer events (兼容鼠标 + 触屏), 长按语义
        onPointerDown={onPointerDown}
        onPointerUp={stop}
        onPointerLeave={stop}
        onPointerCancel={stop}
        data-testid="voice-recorder-button"
        aria-label={buttonLabel}
      >
        {renderIcon()}
        {label}
      </Button>
      {isRecording && renderStatus()}
    </div>
  );
};
