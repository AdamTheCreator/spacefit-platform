import { useMemo, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, ChevronsUpDown } from 'lucide-react';

// ---------------------------------------------------------------------------
// DataTable — a dense, sortable, optionally-selectable table for workbench
// surfaces (DESIGN.md → "Parsed metadata"). Column-config driven: each column
// supplies a `render` for the cell and an optional `sortValue` to make the
// header clickable. Token-styled (dark-mode safe), compact rows. Cell content
// is whatever you return from `render`, so bespoke cells (logos, badges) work.
// ---------------------------------------------------------------------------

export type SortDir = 'asc' | 'desc';

export interface Column<T> {
  /** Stable key; also used as the sort identifier. */
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  /** Return a comparable value to make this column sortable. Omit = not sortable. */
  sortValue?: (row: T) => string | number | null | undefined;
  width?: number | string;
  align?: 'left' | 'right';
  /** Extra classes applied to both the header and the body cell. */
  cellClassName?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  initialSort?: { key: string; dir: SortDir };
  /** Render a leading checkbox column. */
  selectable?: boolean;
  isSelected?: (row: T) => boolean;
  onToggleRow?: (row: T) => void;
  allSelected?: boolean;
  onToggleAll?: () => void;
  /** Shown in place of the body when there are no rows. */
  empty?: ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  initialSort,
  selectable,
  isSelected,
  onToggleRow,
  allSelected,
  onToggleAll,
  empty,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<{ key: string; dir: SortDir } | null>(initialSort ?? null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const dir = sort.dir === 'asc' ? 1 : -1;
    const getVal = col.sortValue;
    return [...rows].sort((a, b) => {
      const av = getVal(a);
      const bv = getVal(b);
      // Nulls always sort last, regardless of direction.
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
      return String(av).localeCompare(String(bv)) * dir;
    });
  }, [rows, sort, columns]);

  const handleSort = (key: string) => {
    setSort((prev) => {
      if (prev?.key !== key) return { key, dir: 'asc' };
      if (prev.dir === 'asc') return { key, dir: 'desc' };
      return null; // third click clears sorting
    });
  };

  const colSpan = columns.length + (selectable ? 1 : 0);

  return (
    <div className="rounded-xl border border-[var(--border-default)] overflow-hidden bg-[var(--bg-secondary)]">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="bg-[var(--bg-tertiary)] border-b border-[var(--border-default)]">
            {selectable && (
              <th className="w-12 px-3.5 py-2.5" onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={!!allSelected}
                  onChange={onToggleAll}
                  className="cursor-pointer accent-[var(--accent)]"
                  aria-label="Select all rows"
                />
              </th>
            )}
            {columns.map((col) => {
              const sortable = !!col.sortValue;
              const isActive = sort?.key === col.key;
              return (
                <th
                  key={col.key}
                  style={{ width: col.width }}
                  className={`px-3.5 py-2.5 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-industrial-secondary ${
                    col.align === 'right' ? 'text-right' : 'text-left'
                  } ${col.cellClassName ?? ''}`}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => handleSort(col.key)}
                      className={`inline-flex items-center gap-1 hover:text-industrial transition-colors ${
                        col.align === 'right' ? 'flex-row-reverse' : ''
                      } ${isActive ? 'text-industrial' : ''}`}
                    >
                      {col.header}
                      {isActive ? (
                        sort?.dir === 'asc' ? (
                          <ChevronUp size={12} className="text-[var(--accent)]" />
                        ) : (
                          <ChevronDown size={12} className="text-[var(--accent)]" />
                        )
                      ) : (
                        <ChevronsUpDown size={12} className="opacity-40" />
                      )}
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={colSpan} className="px-4 py-12 text-center text-industrial-muted text-[13px]">
                {empty ?? 'No results.'}
              </td>
            </tr>
          ) : (
            sorted.map((row) => {
              const id = rowKey(row);
              return (
                <tr
                  key={id}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={`border-b border-[var(--border-default)] last:border-0 transition-colors ${
                    onRowClick ? 'cursor-pointer hover:bg-[var(--bg-tertiary)]' : ''
                  }`}
                >
                  {selectable && (
                    <td className="px-3.5 py-3 align-middle" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={!!isSelected?.(row)}
                        onChange={() => onToggleRow?.(row)}
                        className="cursor-pointer accent-[var(--accent)]"
                        aria-label="Select row"
                      />
                    </td>
                  )}
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-3.5 py-3 align-middle ${
                        col.align === 'right' ? 'text-right tabular-nums' : ''
                      } ${col.cellClassName ?? ''}`}
                    >
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

export default DataTable;
