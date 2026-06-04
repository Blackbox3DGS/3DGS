interface TrajectoryDiagramProps {
  /** SVG viewBox 내 실제 그리기 영역 크기 조정 (기본: compact=false) */
  compact?: boolean;
}

export function TrajectoryDiagram({ compact = false }: TrajectoryDiagramProps) {
  const strokeA = compact ? 14 : 18;
  const strokeB = compact ? 14 : 18;
  const nodeR = compact ? 3 : 4;
  const dotR = compact ? 1.2 : 1.5;
  const fontSize = { label: compact ? 9 : 10, speed: compact ? 7.5 : 8, angle: compact ? 7 : 9, tick: compact ? 6.5 : 6.5 };

  return (
    <svg
      viewBox="0 0 480 360"
      className="w-full h-full"
      preserveAspectRatio="xMidYMid meet"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Grid */}
      <g stroke="rgba(92,191,174,0.05)" strokeWidth="0.5">
        {[0,1,2,3,4,5,6,7,8].map(i => (
          <line key={`h${i}`} x1="28" y1={28 + i * 38} x2="452" y2={28 + i * 38} />
        ))}
        {[0,1,2,3,4,5,6,7,8].map(i => (
          <line key={`v${i}`} x1={28 + i * 53} y1="28" x2={28 + i * 53} y2="340" />
        ))}
      </g>

      {/* Trajectory A — teal */}
      <path d="M72 70 C130 88, 175 125, 242 182" stroke="rgba(41,146,131,0.12)" strokeWidth={strokeA} strokeLinecap="round" fill="none" />
      <path d="M72 70 C130 88, 175 125, 242 182" stroke="#5cbfae" strokeOpacity="0.45" strokeWidth="1" strokeDasharray="5 4" fill="none" />

      {compact && (
        <>
          <circle cx="100" cy="80" r={dotR} fill="#5cbfae" fillOpacity="0.3" />
          <text x="104" y="78" fontSize={fontSize.tick} fill="rgba(255,255,255,0.3)" fontFamily="ui-monospace, monospace">f.210</text>
          <circle cx="140" cy="100" r={dotR} fill="#5cbfae" fillOpacity="0.35" />
          <text x="144" y="98" fontSize={fontSize.tick} fill="rgba(255,255,255,0.3)" fontFamily="ui-monospace, monospace">f.420</text>
          <circle cx="182" cy="126" r={dotR} fill="#5cbfae" fillOpacity="0.4" />
          <text x="186" y="124" fontSize={fontSize.tick} fill="rgba(255,255,255,0.3)" fontFamily="ui-monospace, monospace">f.630</text>
          <circle cx="216" cy="156" r={dotR} fill="#5cbfae" fillOpacity="0.45" />
        </>
      )}

      {/* Trajectory B — light green */}
      <path d="M408 290 C355 274, 310 238, 242 182" stroke="rgba(77,138,107,0.12)" strokeWidth={strokeB} strokeLinecap="round" fill="none" />
      <path d="M408 290 C355 274, 310 238, 242 182" stroke="#4d8a6b" strokeOpacity="0.4" strokeWidth="1" strokeDasharray="5 4" fill="none" />

      {compact && (
        <>
          <circle cx="380" cy="282" r={dotR} fill="#4d8a6b" fillOpacity="0.3" />
          <text x="362" y="278" fontSize={fontSize.tick} fill="rgba(255,255,255,0.3)" fontFamily="ui-monospace, monospace">f.195</text>
          <circle cx="342" cy="260" r={dotR} fill="#4d8a6b" fillOpacity="0.35" />
          <circle cx="300" cy="236" r={dotR} fill="#4d8a6b" fillOpacity="0.4" />
          <circle cx="268" cy="210" r={dotR} fill="#4d8a6b" fillOpacity="0.45" />
        </>
      )}

      {/* Impact zone */}
      <circle cx="242" cy="182" r={compact ? 18 : 22} fill="#299283" fillOpacity="0.04" />
      <circle cx="242" cy="182" r={compact ? 7 : 9} fill="#299283" fillOpacity={compact ? 0.08 : 0.18} />
      <circle cx="242" cy="182" r="2" fill="#299283" fillOpacity="0.85" />

      {/* Angle arc */}
      <path d="M230 172 A15 15 0 0 1 254 192" stroke="rgba(255,255,255,0.18)" strokeWidth="0.6" fill="none" />
      <text x="256" y="172" fontSize={fontSize.angle} fill="#5cbfae" fillOpacity="0.7" fontFamily="ui-monospace, monospace">47.2°</text>

      {/* Vehicle A node */}
      <circle cx="72" cy="70" r={nodeR} fill="#299283" fillOpacity="0.12" stroke="#5cbfae" strokeOpacity="0.3" strokeWidth="0.7" />
      <circle cx="72" cy="70" r={dotR} fill="#5cbfae" fillOpacity="0.85" />
      <text x="80" y="67" fontSize={fontSize.label} fill="#5cbfae" fillOpacity="0.7" fontFamily="ui-monospace, monospace">차량 A</text>
      <text x="80" y="78" fontSize={fontSize.speed} fill="rgba(255,255,255,0.35)" fontFamily="ui-monospace, monospace">62.4 km/h</text>

      {/* Vehicle B node */}
      <circle cx="408" cy="290" r={nodeR} fill="#4d8a6b" fillOpacity="0.15" stroke="#4d8a6b" strokeOpacity="0.4" strokeWidth="0.7" />
      <circle cx="408" cy="290" r={dotR} fill="#4d8a6b" fillOpacity="0.85" />
      <text x="376" y="312" fontSize={fontSize.label} fill="#4d8a6b" fillOpacity="0.7" fontFamily="ui-monospace, monospace">차량 B</text>
      <text x="364" y="323" fontSize={fontSize.speed} fill="rgba(255,255,255,0.35)" fontFamily="ui-monospace, monospace">44.8 km/h</text>

      {/* Impact label */}
      <text x="200" y="206" fontSize={compact ? 7.5 : 9} fill="rgba(255,255,255,0.45)" fontFamily="ui-monospace, monospace">충돌 지점</text>
      <text x="200" y="216" fontSize={compact ? 7 : 8} fill="rgba(255,255,255,0.3)" fontFamily="ui-monospace, monospace">14:23:07.412</text>

      {/* Distance ruler (compact only) */}
      {compact && (
        <>
          <line x1="72" y1="340" x2="408" y2="340" stroke="rgba(255,255,255,0.08)" strokeWidth="0.5" />
          <line x1="72"  y1="336" x2="72"  y2="344" stroke="rgba(255,255,255,0.1)" strokeWidth="0.5" />
          <line x1="242" y1="336" x2="242" y2="344" stroke="rgba(255,255,255,0.1)" strokeWidth="0.5" />
          <line x1="408" y1="336" x2="408" y2="344" stroke="rgba(255,255,255,0.1)" strokeWidth="0.5" />
          <text x="48"  y="348" fontSize="6.5" fill="rgba(255,255,255,0.2)" fontFamily="ui-monospace, monospace">0m</text>
          <text x="228" y="348" fontSize="6.5" fill="rgba(255,255,255,0.2)" fontFamily="ui-monospace, monospace">24m</text>
          <text x="396" y="348" fontSize="6.5" fill="rgba(255,255,255,0.2)" fontFamily="ui-monospace, monospace">48m</text>
          <text x="12" y="32"  fontSize="6" fill="rgba(255,255,255,0.15)" fontFamily="ui-monospace, monospace">N</text>
          <text x="12" y="338" fontSize="6" fill="rgba(255,255,255,0.15)" fontFamily="ui-monospace, monospace">S</text>
        </>
      )}
    </svg>
  );
}
