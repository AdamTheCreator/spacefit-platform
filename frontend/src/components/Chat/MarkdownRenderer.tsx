import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
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

// Chart color palette
const CHART_COLORS = [
  '#8b5cf6', // purple
  '#06b6d4', // cyan
  '#10b981', // emerald
  '#f59e0b', // amber
  '#ef4444', // red
  '#ec4899', // pink
  '#6366f1', // indigo
  '#14b8a6', // teal
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
      <div className="my-3 sm:my-4 p-3 sm:p-4 bg-gray-800/50 rounded-lg border border-gray-700 -mx-2 sm:mx-0">
        <h4 className="text-xs sm:text-sm font-medium text-gray-300 mb-2 sm:mb-3">{chartData.title}</h4>
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
              contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
              labelStyle={{ color: '#9ca3af' }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px' }}
              formatter={(value) => <span className="text-gray-300">{value}</span>}
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
      <div className="my-3 sm:my-4 p-3 sm:p-4 bg-gray-800/50 rounded-lg border border-gray-700 -mx-2 sm:mx-0">
        <h4 className="text-xs sm:text-sm font-medium text-gray-300 mb-2 sm:mb-3">{chartData.title}</h4>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData.data} margin={{ top: 10, right: 5, left: -15, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey={xKey}
              tick={{ fill: '#9ca3af', fontSize: 10 }}
              axisLine={{ stroke: '#4b5563' }}
            />
            <YAxis
              tick={{ fill: '#9ca3af', fontSize: 10 }}
              axisLine={{ stroke: '#4b5563' }}
              width={35}
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
              labelStyle={{ color: '#9ca3af' }}
              cursor={{ fill: 'rgba(139, 92, 246, 0.1)' }}
            />
            <Bar
              dataKey={dataKey}
              fill="#8b5cf6"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return null;
}

// Custom markdown components with Tailwind styling
const markdownComponents: Components = {
  // Headings
  h1: ({ children }) => (
    <h1 className="text-2xl font-bold text-white mt-6 mb-4 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-xl font-bold text-white mt-5 mb-3 first:mt-0 border-b border-gray-700 pb-2">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-lg font-semibold text-white mt-4 mb-2">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-base font-semibold text-gray-200 mt-3 mb-2">{children}</h4>
  ),

  // Paragraphs
  p: ({ children }) => (
    <p className="text-gray-300 mb-3 leading-relaxed">{children}</p>
  ),

  // Strong/Bold
  strong: ({ children }) => (
    <strong className="font-semibold text-white">{children}</strong>
  ),

  // Emphasis/Italic
  em: ({ children }) => (
    <em className="text-gray-400 italic">{children}</em>
  ),

  // Lists
  ul: ({ children }) => (
    <ul className="list-none space-y-1.5 mb-4 ml-1">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside space-y-1.5 mb-4 text-gray-300">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="text-gray-300 flex items-start gap-2">
      <span className="text-purple-400 mt-1.5">•</span>
      <span className="flex-1">{children}</span>
    </li>
  ),

  // Tables - fully styled with responsive padding
  table: ({ children }) => (
    <div className="my-3 sm:my-4 overflow-x-auto rounded-lg border border-gray-700 -mx-2 sm:mx-0">
      <table className="w-full text-xs sm:text-sm min-w-[300px]">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-gray-800/80 border-b border-gray-700">{children}</thead>
  ),
  tbody: ({ children }) => (
    <tbody className="divide-y divide-gray-700/50">{children}</tbody>
  ),
  tr: ({ children }) => (
    <tr className="hover:bg-gray-800/30 transition-colors">{children}</tr>
  ),
  th: ({ children }) => (
    <th className="px-2 sm:px-4 py-2 sm:py-3 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-300">{children}</td>
  ),

  // Code
  code: ({ children, className }) => {
    const isInline = !className;
    if (isInline) {
      return (
        <code className="px-1.5 py-0.5 bg-gray-800 text-purple-300 rounded text-sm font-mono">
          {children}
        </code>
      );
    }
    return (
      <code className="block p-4 bg-gray-800 rounded-lg text-gray-300 text-sm font-mono overflow-x-auto">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-4">{children}</pre>
  ),

  // Blockquotes
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-purple-500 pl-4 my-4 text-gray-400 italic">
      {children}
    </blockquote>
  ),

  // Horizontal rule
  hr: () => (
    <hr className="my-6 border-gray-700" />
  ),

  // Links
  a: ({ href, children }) => (
    <a
      href={href}
      className="text-purple-400 hover:text-purple-300 underline underline-offset-2"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
};

export function MarkdownRenderer({ content, agentType }: MarkdownRendererProps) {
  // Determine chart type based on agent
  let chartType: 'demographics' | 'traffic' | 'void' | null = null;
  if (agentType === 'demographics') chartType = 'demographics';
  if (agentType === 'foot-traffic') chartType = 'traffic';
  if (agentType === 'void-analysis') chartType = 'void';

  const chartData = chartType ? extractChartData(content, chartType) : null;

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
