import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import type { VideoResult } from "@/types/app";

interface Props {
  video: VideoResult;
  onClose: () => void;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function VideoPlayer({ video, onClose }: Props) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 bg-background/95 backdrop-blur flex"
      onClick={(e) => {
        if (e.target === overlayRef.current) {
          onClose();
        }
      }}
    >
      <div className="flex-1 flex items-center justify-center relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-foreground/10 hover:bg-foreground/20 flex items-center justify-center transition-colors z-10"
        >
          <X className="w-4 h-4" />
        </button>
        <video
          controls
          autoPlay
          className="max-h-[90vh] max-w-[90%] rounded-lg"
          src={video.url}
        >
          <source src={video.url} />
        </video>
      </div>
      <div className="w-72 border-l border-border p-4 space-y-3 overflow-auto shrink-0 hidden md:block">
        <h2 className="text-sm font-medium truncate">{video.filename}</h2>
        <div className="text-xs text-muted-foreground space-y-1">
          {video.folder && (
            <p>
              <span className="text-foreground/60">Folder: </span>
              {video.folder}
            </p>
          )}
          {video.dateTaken && (
            <p>
              <span className="text-foreground/60">Taken: </span>
              {video.dateTaken}
            </p>
          )}
          {video.duration != null && (
            <p>
              <span className="text-foreground/60">Duration: </span>
              {formatDuration(video.duration)}
            </p>
          )}
          {video.width != null && video.height != null && (
            <p>
              <span className="text-foreground/60">Dimensions: </span>
              {video.width}&times;{video.height}
            </p>
          )}
          {video.score != null && (
            <p>
              <span className="text-foreground/60">Score: </span>
              {Math.round(video.score * 100)}%
            </p>
          )}
          {video.timestamp != null && (
            <p>
              <span className="text-foreground/60">Match: </span>
              {formatDuration(video.timestamp)}
              {video.keyframeIndex != null && video.totalKeyframes != null && (
                <> · Scene {video.keyframeIndex + 1} of {video.totalKeyframes}</>
              )}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
