import { useEffect, useRef, useState } from 'react';

// 재생 타임라인 — 스크러버 + 재생/정지 + 사고/최근접 시점 마커.
//
// 마커 종류(부모가 우선순위를 정해 내려줌):
//   collision = 프레임 증거로 검출된 충돌(빨강 ⚠)
//   manual    = 사용자가 영상을 보고 지정한 사고 시점(주황 ✎)
//   closest   = 궤적상 최근접 쌍(틸 ○, 참고용 — 충돌 근거 아님)
//
// 현재 프레임은 100 ms 간격으로 getFrame()을 폴링해 이 작은 컴포넌트만
// 리렌더한다(엔진 애니메이션 루프에 React를 끌어들이지 않기 위함).

type MarkerKind = 'collision' | 'manual' | 'closest';

interface TimelineBarProps {
  durFrames: number;                 // 마지막 frame_idx
  fps: number;
  markerFrame: number | null;
  markerKind: MarkerKind | null;
  playing: boolean;
  onTogglePlay: () => void;
  onSeek: (frame: number) => void;   // 호출측에서 일시정지 처리
  getFrame: () => number;            // 엔진의 현재 프레임
}

const MARKER_STYLE: Record<MarkerKind, { color: string; jumpLabel: string; title: string }> = {
  collision: { color: '#ef4444', jumpLabel: '⚠ 충돌 시점', title: '영상 증거로 검출된 충돌 프레임으로 이동' },
  manual: { color: '#f59e0b', jumpLabel: '✎ 지정 시점', title: '수동 지정한 사고 프레임으로 이동' },
  closest: { color: '#299283', jumpLabel: '○ 최근접', title: '궤적상 최근접 프레임(참고용 — 충돌 근거 아님)' },
};

export function TimelineBar({
  durFrames, fps, markerFrame, markerKind, playing, onTogglePlay, onSeek, getFrame,
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
  const markerPct =
    markerFrame != null && durFrames > 0 ? (markerFrame / durFrames) * 100 : null;
  const style = markerKind ? MARKER_STYLE[markerKind] : null;

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
          {markerPct != null && style && (
            <div
              className="pointer-events-none absolute -top-1.5 z-10 -translate-x-1/2"
              style={{ left: `${markerPct}%` }}
              title={style.title}
            >
              <div className="h-2 w-2 rotate-45" style={{ background: style.color }} />
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
              background: `linear-gradient(to right, #299283 ${pct}%, #dae3dd ${pct}%)`,
            }}
          />
        </div>

        <div className="w-28 shrink-0 text-right font-mono text-xs text-[#5a665e]">
          {(frame / fps).toFixed(1)}s / {(durFrames / fps).toFixed(1)}s
        </div>

        {markerFrame != null && style && (
          <button
            onClick={() => { setFrame(markerFrame); onSeek(markerFrame); }}
            className="shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
            style={{ background: markerKind === 'closest' ? '#299283' : markerKind === 'manual' ? '#b45309' : '#20543d' }}
            title={style.title}
          >
            {style.jumpLabel}
          </button>
        )}
      </div>
    </div>
  );
}
