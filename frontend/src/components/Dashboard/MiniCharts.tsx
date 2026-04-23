// Space Goose mini-chart helpers. Tiny hand-rolled SVG charts matching the
// Space Goose design bundle. No runtime library.

interface LineChartProps {
  data: number[];
  color?: string;
  fill?: boolean;
  height?: number;
}

export function LineChart({
  data,
  color = '#3A5BA0',
  fill = true,
  height = 120,
}: LineChartProps) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const w = 100;
  const pts = data.map<[number, number]>((v, i) => [
    (i * w) / (data.length - 1),
    height - ((v - min) / range) * (height - 16) - 8,
  ]);
  const path = pts
    .map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(2) + ',' + p[1].toFixed(2))
    .join(' ');
  const gid = 'g' + Math.random().toString(36).slice(2, 7);
  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      style={{ width: '100%', height, display: 'block' }}
    >
      <defs>
        <linearGradient id={gid} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.22" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={path + ` L${w},${height} L0,${height} Z`} fill={`url(#${gid})`} />}
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth="1.4"
        vectorEffect="non-scaling-stroke"
      />
      <circle
        cx={pts[pts.length - 1][0]}
        cy={pts[pts.length - 1][1]}
        r="1.4"
        fill="#FF8A3D"
      />
    </svg>
  );
}

interface BarChartProps {
  data: number[];
  color?: string;
  height?: number;
}

export function BarChart({ data, color = '#3A5BA0', height = 120 }: BarChartProps) {
  const max = Math.max(...data);
  const w = 100;
  const gap = 1.2;
  const bw = (w - gap * (data.length - 1)) / data.length;
  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      style={{ width: '100%', height, display: 'block' }}
    >
      {data.map((v, i) => {
        const bh = (v / max) * (height - 8);
        return (
          <rect
            key={i}
            x={i * (bw + gap)}
            y={height - bh}
            width={bw}
            height={bh}
            fill={color}
            opacity={i === data.length - 1 ? 1 : 0.55}
            rx="0.5"
          />
        );
      })}
    </svg>
  );
}
