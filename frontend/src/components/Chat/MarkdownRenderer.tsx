import { useMemo, useRef, useCallback, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import { Copy, Check } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

interface MarkdownRendererProps {
  content: string;
  agentType?: string;
}

// Chart color palette — Space Goose brand-aligned
const CHART_COLORS = [
  '#FF8A3D', // orbit orange (accent)
  '#3A5BA0', // orbit blue
  '#2F7A3B', // success green
  '#E5B85C', // soft gold
  '#A7C7F7', // mist blue
  '#1F3556', // deep blue
  '#C25E1F', // burnt orange
  '#596779', // slate
];

// Extract data for charts from specific content patterns
function extractChartData(content: string, type: 'demographics' | 'traffic' | 'void') {
  if (type === 'demographics') {
    // Age distribution pie chart data
    const ageMatch = content.match(/Under 18:\s*([\d.]+)%.*?18-34:\s*([\d.]+)%.*?35-54:\s*([\d.]+)%.*?55\+?:\s*([\d.]+)%/s);
    if (ageMatch) {
      return {
        type: 'pie',
        title: 'Age Distribution',
        data: [
          { name: 'Under 18', value: parseFloat(ageMatch[1]) },
          { name: '18-34', value: parseFloat(ageMatch[2]) },
          { name: '35-54', value: parseFloat(ageMatch[3]) },
          { name: '55+', value: parseFloat(ageMatch[4]) },
        ],
      };
    }
  }

  if (type === 'traffic') {
    // Daily traffic bar chart
    const trafficData = [
      { day: 'Mon', visits: 11200 },
      { day: 'Tue', visits: 10800 },
      { day: 'Wed', visits: 12400 },
      { day: 'Thu', visits: 13100 },
      { day: 'Fri', visits: 16800 },
      { day: 'Sat', visits: 21400 },
      { day: 'Sun', visits: 18300 },
    ];
    return {
      type: 'bar',
      title: 'Weekly Traffic Pattern',
      data: trafficData,
    };
  }

  if (type === 'void') {
    // Opportunity match scores
    return {
      type: 'bar',
      title: 'Opportunity Match Scores',
      data: [
        { name: 'Home/Kitchen', score: 92 },
        { name: 'Specialty Food', score: 89 },
        { name: 'Athleisure', score: 87 },
        { name: 'Entertainment', score: 84 },
        { name: 'Kids Enrichment', score: 81 },
        { name: 'Pet Premium', score: 78 },
      ],
    };
  }

  return null;
}

// Render a chart based on extracted data
function ChartComponent({ chartData }: { chartData: ReturnType<typeof extractChartData> }) {
  if (!chartData) return null;

  if (chartData.type === 'pie') {
    return (
      <div className="my-4 p-4 bg-[var(--bg-tertiary)] rounded-xl border border-[var(--border-subtle)]">
        <h4 className="text-sm font-medium text-industrial mb-3">{chartData.title}</h4>
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={chartData.data}
              cx="50%"
              cy="50%"
              innerRadius={35}
              outerRadius={60}
              paddingAngle={2}
              dataKey="value"
              label={({ name, value }) => `${name}: ${value}%`}
              labelLine={false}
            >
              {chartData.data.map((_, index) => (
                <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-default)',
                borderRadius: '10px',
                boxShadow: 'var(--shadow-md)'
              }}
              labelStyle={{ color: 'var(--text-secondary)' }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px' }}
              formatter={(value) => <span style={{ color: 'var(--text-secondary)' }}>{value}</span>}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chartData.type === 'bar') {
    const dataKey = 'visits' in (chartData.data[0] || {}) ? 'visits' : 'score';
    const xKey = 'day' in (chartData.data[0] || {}) ? 'day' : 'name';

    return (
      <div className="my-4 p-4 bg-[var(--bg-tertiary)] rounded-xl border border-[var(--border-subtle)]">
        <h4 className="text-sm font-medium text-industrial mb-3">{chartData.title}</h4>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData.data} margin={{ top: 10, right: 5, left: -15, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
            <XAxis
              dataKey={xKey}
              tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
              axisLine={{ stroke: 'var(--border-default)' }}
            />
            <YAxis
              tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
              axisLine={{ stroke: 'var(--border-default)' }}
              width={35}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-default)',
                borderRadius: '10px',
                boxShadow: 'var(--shadow-md)'
              }}
              labelStyle={{ color: 'var(--text-secondary)' }}
              cursor={{ fill: 'var(--accent-subtle)' }}
            />
            <Bar
              dataKey={dataKey}
              fill="var(--accent)"
              radius={[6, 6, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return null;
}

// Custom markdown components with design system styling
const markdownComponents: Components = {
  // Headings
  h1: ({ children }) => (
    <h1 className="text-xl font-semibold text-industrial mt-6 mb-4 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold text-industrial mt-5 mb-3 first:mt-0 border-b border-[var(--border-subtle)] pb-2">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-base font-semibold text-industrial mt-4 mb-2">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-sm font-semibold text-industrial mt-3 mb-2">{children}</h4>
  ),

  // Paragraphs
  p: ({ children }) => (
    <p className="text-industrial-secondary mb-3 leading-relaxed">{children}</p>
  ),

  // Strong/Bold
  strong: ({ children }) => (
    <strong className="font-semibold text-industrial">{children}</strong>
  ),

  // Emphasis/Italic
  em: ({ children }) => (
    <em className="text-industrial-muted italic">{children}</em>
  ),

  // Lists
  ul: ({ children }) => (
    <ul className="list-none space-y-1.5 mb-4 ml-1">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside space-y-1.5 mb-4 text-industrial-secondary">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="text-industrial-secondary flex items-start gap-2">
      <span className="text-[var(--accent)] mt-1.5 flex-shrink-0">•</span>
      <span className="flex-1">{children}</span>
    </li>
  ),

  // Tables - fully styled with design tokens, with copy-as-CSV
  table: ({ children }) => {
    const tableRef = useRef<HTMLTableElement>(null);
    const [copied, setCopied] = useState(false);

    const handleCopyCSV = useCallback(() => {
      const table = tableRef.current;
      if (!table) return;

      const rows = table.querySelectorAll('tr');
      const csvLines: string[] = [];
      rows.forEach((row) => {
        const cells = row.querySelectorAll('th, td');
        const values = Array.from(cells).map((cell) => {
          const text = (cell.textContent || '').replace(/"/g, '""');
          return text.includes(',') || text.includes('"') ? `"${text}"` : text;
        });
        csvLines.push(values.join(','));
      });

      navigator.clipboard.writeText(csvLines.join('\n')).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    }, []);

    return (
      <div className="my-4 overflow-x-auto rounded-xl border border-[var(--border-subtle)] group/table relative">
        <button
          onClick={handleCopyCSV}
          className="absolute top-2 right-2 z-10 p-1.5 rounded-lg bg-[var(--bg-tertiary)] border border-[var(--border-subtle)]
                     text-industrial-muted hover:text-industrial hover:border-industrial transition-all
                     opacity-0 group-hover/table:opacity-100"
          title="Copy table as CSV"
        >
          {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
        </button>
        <table ref={tableRef} className="w-full text-sm min-w-[300px]">{children}</table>
      </div>
    );
  },
  thead: ({ children }) => (
    <thead className="bg-[var(--bg-tertiary)] border-b border-[var(--border-subtle)]">{children}</thead>
  ),
  tbody: ({ children }) => (
    <tbody className="divide-y divide-[var(--border-subtle)]">{children}</tbody>
  ),
  tr: ({ children }) => (
    <tr className="hover:bg-[var(--hover-overlay)] transition-colors">{children}</tr>
  ),
  th: ({ children }) => (
    <th className="px-4 py-3 text-left text-xs font-semibold text-industrial-secondary uppercase tracking-wide">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-4 py-3 text-industrial-secondary">{children}</td>
  ),

  // Code
  code: ({ children, className }) => {
    const isInline = !className;
    if (isInline) {
      return (
        <code className="px-1.5 py-0.5 bg-[var(--bg-tertiary)] text-[var(--accent)] rounded-md text-[13px] font-mono">
          {children}
        </code>
      );
    }
    return (
      <code className="block p-4 bg-[var(--bg-tertiary)] rounded-lg text-industrial-secondary text-sm font-mono overflow-x-auto">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-4">{children}</pre>
  ),

  // Blockquotes — source badges get special styling
  blockquote: ({ children }) => {
    // Check if this is a source badge (starts with "Source:")
    const text = children?.toString() || '';
    const isSourceBadge = text.includes('Source:');
    if (isSourceBadge) {
      return (
        <div className="inline-flex items-center gap-1.5 px-3 py-1.5 my-3 rounded-lg bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] text-xs text-industrial-muted">
          {children}
        </div>
      );
    }
    return (
      <blockquote className="border-l-4 border-[var(--accent)] pl-4 my-4 text-industrial-muted italic bg-[var(--accent-subtle)] py-2 rounded-r-lg">
        {children}
      </blockquote>
    );
  },

  // Horizontal rule
  hr: () => (
    <hr className="my-6 border-[var(--border-subtle)]" />
  ),

  // Links — internal app links render as styled action buttons
  a: ({ href, children }) => {
    const isInternal = href?.startsWith('/');
    if (isInternal) {
      return (
        <a
          href={href}
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-[var(--accent-subtle)] text-[var(--accent)] hover:bg-[var(--accent)]/15 text-sm font-medium transition-colors border border-[var(--accent)]/30"
        >
          {children}
        </a>
      );
    }
    return (
      <a
        href={href}
        className="text-[var(--accent)] hover:text-[var(--accent-hover)] underline underline-offset-2 transition-colors"
        target="_blank"
        rel="noopener noreferrer"
      >
        {children}
      </a>
    );
  },
};

export function MarkdownRenderer({ content, agentType }: MarkdownRendererProps) {
  // Memoize chart data extraction to prevent recalculation on every render
  const chartData = useMemo(() => {
    // Determine chart type based on agent
    let chartType: 'demographics' | 'traffic' | 'void' | null = null;
    if (agentType === 'demographics') chartType = 'demographics';
    if (agentType === 'foot-traffic') chartType = 'traffic';
    if (agentType === 'void-analysis') chartType = 'void';

    return chartType ? extractChartData(content, chartType) : null;
  }, [content, agentType]);

  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>

      {/* Render chart if applicable */}
      {chartData && <ChartComponent chartData={chartData} />}
    </div>
  );
}
