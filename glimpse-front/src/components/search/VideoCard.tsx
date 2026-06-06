import { Play } from "lucide-react";
import type { VideoResult } from "@/types/app";
import { useState } from "react";
import { VideoPlayer } from "@/components/search/VideoPlayer";

interface Props {
  video: VideoResult;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function VideoCard({ video }: Props) {
  const [playerOpen, setPlayerOpen] = useState(false);

  return (
    <>
      <div
        className="group relative rounded-lg overflow-hidden bg-card border border-border cursor-pointer hover:border-primary/30 transition-colors"
        onClick={() => setPlayerOpen(true)}
      >
        <div className="aspect-[4/3] overflow-hidden">
          <img
            src={video.thumbnailUrl ?? video.url}
            alt={video.filename}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
        </div>
        <div className="absolute inset-0 bg-foreground/0 group-hover:bg-foreground/10 transition-colors" />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-12 h-12 rounded-full bg-foreground/70 backdrop-blur flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
            <Play className="w-5 h-5 text-background ml-0.5" />
          </div>
        </div>
        {video.duration != null && (
          <div className="absolute bottom-2 left-2">
            <div className="px-1.5 py-0.5 rounded bg-background/80 backdrop-blur text-[10px] text-foreground">
              {formatDuration(video.duration)}
            </div>
          </div>
        )}
        <div className="px-2 py-1.5">
          <p className="text-[11px] text-muted-foreground truncate">{video.filename}</p>
        </div>
      </div>
      {playerOpen && (
        <VideoPlayer
          video={video}
          onClose={() => setPlayerOpen(false)}
        />
      )}
    </>
  );
}
