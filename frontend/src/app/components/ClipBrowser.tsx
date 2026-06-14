import { useEffect, useState } from 'react';
import { Viewer3D } from './Viewer3D';

// 사고영상 배치 결과 스크리닝용 — public/clips/manifest.json 을 읽어 드롭다운으로
// 클립을 전환하며 배경+차량을 빠르게 훑어보고 시연용 클립을 고른다.
interface Clip {
  id: string;
  title?: string;
  splat: string;       // public/clips/ 기준 파일명
  vehicles: string;
}

export function ClipBrowser() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [sel, setSel] = useState<string>('');
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch('/clips/manifest.json')
      .then((r) => { if (!r.ok) throw new Error(`manifest ${r.status}`); return r.json(); })
      .then((d) => {
        const list: Clip[] = Array.isArray(d?.clips) ? d.clips : [];
        setClips(list);
        if (list.length) setSel(list[0].id);
      })
      .catch((e) => setErr(String(e?.message ?? e)));
  }, []);

  const cur = clips.find((c) => c.id === sel);
  const idx = clips.findIndex((c) => c.id === sel);
  const go = (delta: number) => {
    if (!clips.length) return;
    const n = (idx + delta + clips.length) % clips.length;
    setSel(clips[n].id);
  };

  return (
    <div className="min-h-screen bg-[#0e1512] p-6 text-[#dfe7e2]">
      <div className="mx-auto max-w-[1200px]">
        <div className="mb-4 flex items-center gap-3">
          <h1 className="text-lg font-semibold">사고영상 클립 브라우저</h1>
          <span className="text-xs text-[#8a9590]">{clips.length}개</span>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={() => go(-1)}
              disabled={clips.length < 2}
              className="rounded-md border border-[#2a3a33] bg-[#16201b] px-2.5 py-1.5 text-sm disabled:opacity-40"
            >◀</button>
            <select
              value={sel}
              onChange={(e) => setSel(e.target.value)}
              className="rounded-md border border-[#2a3a33] bg-[#16201b] px-3 py-1.5 text-sm"
            >
              {clips.map((c) => (<option key={c.id} value={c.id}>{c.title ?? c.id}</option>))}
            </select>
            <button
              onClick={() => go(1)}
              disabled={clips.length < 2}
              className="rounded-md border border-[#2a3a33] bg-[#16201b] px-2.5 py-1.5 text-sm disabled:opacity-40"
            >▶</button>
          </div>
        </div>

        {err && (
          <p className="text-sm text-amber-400">
            클립 목록을 불러오지 못했습니다 ({err}). 서버 배치 후 <code>public/clips/manifest.json</code> 을 생성하세요.
          </p>
        )}
        {!err && !clips.length && <p className="text-sm text-[#8a9590]">표시할 클립이 없습니다.</p>}

        {cur && (
          <Viewer3D
            key={cur.id}
            jobId={cur.id}
            resultUrl={`/clips/${cur.splat}`}
            trajectoryUrl={`/clips/${cur.vehicles}`}
          />
        )}
      </div>
    </div>
  );
}
