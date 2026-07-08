import { useEffect, useRef, useState } from 'react';

// 재생 타임라인 — 스크러버 + 재생/정지 + 충돌(최근접) 시점 마커.
//
// 현재 프레임은 100 ms 간격으로 getFrame()을 폴링해 이 작은 컴포넌트만
// 리렌더한다(엔진 애니메이션 루프에 React를 끌어들이지 않기 위함 —
// Viewer3D의 uiStateRef 패턴과 동일한 이유).

interface TimelineBarProps {
  durFrames: number;                 // 마지막 frame_idx
  fps: number;
  collisionFrame: number | null;     // 최근접 시점 (마커)
  playing: boolean;
  onTogglePlay: () => void;
  onSeek: (frame: number) => void;   // 호출측에서 일시정지 처리
  getFrame: () => number;            // 엔진의 현재 프레임
}

export function TimelineBar({
  durFrames, fps, collisionFrame, playing, onTogglePlay, onSeek, getFrame,
}: TimelineBarProps) {
  const [frame, setFrame] = useState(0);
  const scrubbing = useRef(false);

  useEffect(() => {
    const id = setInterval(() => {
      if (!scrubbing.current) setFrame(Math.min(durFrames, Math.max(0, getFrame())));
    }, 100);
    return () => clearInterval(id);
  }, [durFrames, getFrame]);

  const pct = durFrames > 0 ? (Math.min(frame, durFrames) / durFrames) * 100 : 0;
  const collisionPct =
    collisionFrame != null && durFrames > 0 ? (collisionFrame / durFrames) * 100 : null;

  return (
    <div className="mt-3 rounded-xl border border-[#dae3dd] bg-white px-4 py-3">
      <div className="flex items-center gap-3">
        <button
          onClick={onTogglePlay}
          className="shrink-0 rounded-lg border border-[#dae3dd] bg-white px-3 py-1.5 text-sm font-medium text-[#5a665e] hover:bg-[#f7f9f8]"
        >
          {playing ? '⏸' : '▶'}
        </button>

        <div className="relative flex-1">
          {/* 충돌 마커 (슬라이더 위 틱) */}
          {collisionPct != null && (
            <div
              className="pointer-events-none absolute -top-1.5 z-10 -translate-x-1/2"
              style={{ left: `${collisionPct}%` }}
              title={`최근접 시점: 프레임 ${collisionFrame}`}
            >
              <div className="h-2 w-2 rotate-45 bg-red-500" />
            </div>
          )}
          <input
            type="range"
            min={0}
            max={Math.max(1, durFrames)}
            step={0.1}
            value={frame}
            onPointerDown={() => { scrubbing.current = true; }}
            onPointerUp={() => { scrubbing.current = false; }}
            onChange={(e) => {
              const f = Number(e.target.value);
              setFrame(f);
              onSeek(f);
            }}
            className="w-full accent-[#299283]"
            style={{
              background: collisionPct != null
                ? `linear-gradient(to right, #299283 ${pct}%, #dae3dd ${pct}%)`
                : undefined,
            }}
          />
        </div>

        <div className="w-28 shrink-0 text-right font-mono text-xs text-[#5a665e]">
          {(frame / fps).toFixed(1)}s / {(durFrames / fps).toFixed(1)}s
        </div>

        {collisionFrame != null && (
          <button
            onClick={() => { setFrame(collisionFrame); onSeek(collisionFrame); }}
            className="shrink-0 rounded-lg bg-[#20543d] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#299283]"
            title="차량 간 거리가 최소가 되는 프레임으로 이동"
          >
            ⚠ 충돌 시점
          </button>
        )}
      </div>
    </div>
  );
}
