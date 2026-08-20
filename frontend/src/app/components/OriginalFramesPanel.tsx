import { useEffect, useRef, useState } from 'react';

// bbox_sequence.json (Stage-03) 형식:
//   { metadata: { num_frames, dynamic_track_ids:[...] },
//     tracks: { "<tid>": { class_name, state, frames: { "<fidx>": { bbox:[x1,y1,x2,y2] } } } } }
interface FrameBox { id: string; cls: string; dynamic: boolean; bbox: [number, number, number, number] }

interface OriginalFramesPanelProps {
  framesPattern: string;       // 예: "/frames/%06d.jpg"
  bboxSequenceUrl: string;     // 예: "/sample3_bbox.json"
  targetIds: string;           // 쉼표구분 입력값
  onTargetIdsChange: (v: string) => void;
}

function framePath(pattern: string, i: number) {
  return pattern.replace('%06d', String(i).padStart(6, '0'));
}

export function OriginalFramesPanel({ framesPattern, bboxSequenceUrl, targetIds, onTargetIdsChange }: OriginalFramesPanelProps) {
  const [open, setOpen] = useState(false);
  const [frameCount, setFrameCount] = useState(0);
  const [frameBoxes, setFrameBoxes] = useState<FrameBox[][]>([]);
  const [allIds, setAllIds] = useState<string[]>([]);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);

  const imgRef = useRef<HTMLImageElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const accRef = useRef<{ last: number; acc: number }>({ last: 0, acc: 0 });

  // bbox_sequence 로드 → 프레임별 박스 인덱싱
  useEffect(() => {
    if (!open || frameBoxes.length) return;
    (async () => {
      try {
        const res = await fetch(bboxSequenceUrl);
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        const n = data?.metadata?.num_frames ?? 0;
        const dynSet = new Set((data?.metadata?.dynamic_track_ids ?? []).map((x: number) => String(x)));
        const perFrame: FrameBox[][] = Array.from({ length: n }, () => []);
        const ids = new Set<string>();
        for (const [tid, tinfo] of Object.entries<any>(data?.tracks ?? {})) {
          if (tid === '-1') continue;
          const cls = tinfo.class_name ?? 'car';
          const dynamic = dynSet.has(tid) || tinfo.state === 'dynamic';
          for (const [f, fd] of Object.entries<any>(tinfo.frames ?? {})) {
            const fi = parseInt(f, 10);
            if (fi >= 0 && fi < n && fd?.bbox) {
              perFrame[fi].push({ id: tid, cls, dynamic, bbox: fd.bbox });
              ids.add(tid);
            }
          }
        }
        setFrameCount(n);
        setFrameBoxes(perFrame);
        setAllIds([...ids].sort((a, b) => parseInt(a) - parseInt(b)));
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('[OriginalFramesPanel] bbox load failed', e);
      }
    })();
  }, [open, bboxSequenceUrl, frameBoxes.length]);

  // 재생 루프 (~10fps × speed)
  useEffect(() => {
    if (!open || !playing || frameCount === 0) return;
    accRef.current = { last: performance.now(), acc: 0 };
    const tick = (now: number) => {
      const dt = now - accRef.current.last; accRef.current.last = now;
      accRef.current.acc += dt * speed;
      const step = 1000 / 10; // 10fps 기준
      if (accRef.current.acc >= step) {
        const adv = Math.floor(accRef.current.acc / step);
        accRef.current.acc -= adv * step;
        setFrame((f) => (f + adv) % frameCount);
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [open, playing, speed, frameCount]);

  // bbox 오버레이 그리기
  const draw = () => {
    const img = imgRef.current, cv = canvasRef.current;
    if (!img || !cv || !img.naturalWidth) return;
    const W = img.clientWidth, H = img.clientHeight;
    cv.width = W; cv.height = H;
    const sx = W / img.naturalWidth, sy = H / img.naturalHeight;
    const ctx = cv.getContext('2d'); if (!ctx) return;
    ctx.clearRect(0, 0, W, H);
    ctx.lineWidth = 2; ctx.font = 'bold 13px sans-serif'; ctx.textBaseline = 'bottom';
    const wanted = targetIds.split(',').map((s) => s.trim()).filter(Boolean);
    for (const b of frameBoxes[frame] ?? []) {
      const sel = wanted.includes(b.id);
      const color = sel ? '#22c55e' : (b.dynamic ? '#f59e0b' : '#94a3b8');
      const [x1, y1, x2, y2] = b.bbox;
      const rx = x1 * sx, ry = y1 * sy, rw = (x2 - x1) * sx, rh = (y2 - y1) * sy;
      ctx.strokeStyle = color; ctx.strokeRect(rx, ry, rw, rh);
      const label = `${b.id}`;
      const tw = ctx.measureText(label).width + 8;
      ctx.fillStyle = color; ctx.fillRect(rx, Math.max(0, ry - 18), tw, 18);
      ctx.fillStyle = '#0a0f1a'; ctx.fillText(label, rx + 4, Math.max(16, ry - 3));
    }
  };

  useEffect(() => { draw(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [frame, frameBoxes, targetIds]);

  return (
    <div className="mt-4 rounded-xl border border-[#dae3dd]">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-[#5a665e] hover:bg-[#f7f9f8] rounded-xl"
      >
        <span>원본 프레임 · 차량 추적 (track id 확인)</span>
        <span className="text-[#8a9590]">{open ? '▲ 접기' : '▼ 펼치기'}</span>
      </button>

      {open && (
        <div className="border-t border-[#dae3dd] p-4 space-y-3">
          {/* 프레임 + bbox 오버레이 */}
          <div className="relative w-full overflow-hidden rounded-lg bg-black">
            <img
              ref={imgRef}
              src={framePath(framesPattern, frame)}
              alt={`frame ${frame}`}
              className="block w-full"
              onLoad={draw}
            />
            <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 h-full w-full" />
            <div className="absolute left-2 top-2 rounded bg-black/55 px-2 py-1 text-xs text-white">
              {frameCount ? `frame ${frame + 1} / ${frameCount}` : '로딩 중…'}
            </div>
          </div>

          {/* 재생 컨트롤 */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setPlaying((v) => !v)}
              className="rounded-lg border border-[#dae3dd] bg-white px-3 py-1.5 text-sm font-medium text-[#5a665e] hover:bg-[#f7f9f8]"
            >
              {playing ? '⏸ 정지' : '▶ 재생'}
            </button>
            <input
              type="range" min={0} max={Math.max(0, frameCount - 1)} value={frame}
              onChange={(e) => { setPlaying(false); setFrame(Number(e.target.value)); }}
              className="flex-1 accent-indigo-600"
            />
            <div className="flex items-center gap-1 text-xs text-[#5a665e]">
              <span>{speed.toFixed(1)}x</span>
              <input type="range" min={0.25} max={3} step={0.25} value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))} className="w-20 accent-indigo-600" />
            </div>
          </div>

          {/* track id 입력 */}
          <div className="space-y-1">
            <label className="text-sm font-semibold text-[#5a665e]">표시할 차량 track id (쉼표 구분)</label>
            <div className="flex gap-2">
              <input
                type="text" value={targetIds}
                onChange={(e) => onTargetIdsChange(e.target.value)}
                placeholder="예: 1, 4, 27   (비우면 전체 표시)"
                className="flex-1 rounded-lg border border-[#dae3dd] px-3 py-2 text-sm text-[#5a665e] focus:outline-none focus:ring-2 focus:ring-indigo-300"
              />
              <button onClick={() => onTargetIdsChange('')}
                className="rounded-lg border border-[#dae3dd] bg-white px-3 py-2 text-sm text-[#5a665e] hover:bg-[#f7f9f8]">전체</button>
            </div>
            {allIds.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-1">
                {allIds.map((id) => {
                  const wanted = targetIds.split(',').map((s) => s.trim()).filter(Boolean);
                  const sel = wanted.includes(id);
                  return (
                    <button key={id}
                      onClick={() => {
                        const set = new Set(wanted);
                        if (set.has(id)) set.delete(id); else set.add(id);
                        onTargetIdsChange([...set].join(', '));
                      }}
                      className={`rounded-md px-2 py-0.5 text-xs border ${sel ? 'bg-[#22c55e] text-white border-[#22c55e]' : 'bg-white text-[#5a665e] border-[#dae3dd] hover:bg-[#f7f9f8]'}`}>
                      {id}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
