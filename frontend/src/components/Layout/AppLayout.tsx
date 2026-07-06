import { useState, useEffect } from 'react';
import { Link, useNavigate, useParams, useLocation } from 'react-router-dom';
import {
  MessageSquare,
  Plus,
  Settings,
  LogOut,
  Users,
  Menu,
  X,
  Kanban,
  Mail,
  Sparkles,
  Home,
  Search as SearchIcon,
  Building2,
  BarChart3,
  Layers,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useChatSessions } from '../../hooks/useChatSessions';
import { usePreferences } from '../../hooks/usePreferences';
import { ConnectorHealthBanner } from '../ConnectorHealthBanner';
import { useSetupNotifications } from '../../hooks/useSetupNotifications';
import { useApiHealth } from '../../hooks/useApiHealth';
import { useCollapsedPreference } from '../../hooks/useCollapsedPreference';

const SIDEBAR_COLLAPSED_KEY = 'spacegoose:sidebar:collapsed';

interface AppLayoutProps {
  children: React.ReactNode;
}

// Space Goose sidebar nav definitions
type NavItem = {
  to: string;
  label: string;
  icon: typeof Home;
  matchPrefixes?: string[];
};

const WORKSPACE_NAV: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: Home },
  { to: '/search', label: 'Find properties', icon: SearchIcon },
  // /properties and /projects both route to ProjectsPage; surface one entry
  // and let the matcher highlight it for either prefix.
  { to: '/properties', label: 'Properties', icon: Building2, matchPrefixes: ['/properties', '/property', '/projects'] },
  { to: '/outreach', label: 'Outreach', icon: Mail },
  { to: '/contacts', label: 'Contacts', icon: Users },
  { to: '/chat', label: 'Chat', icon: MessageSquare, matchPrefixes: ['/chat'] },
];

const DEMO_NAV: NavItem[] = [
  { to: '/analytics', label: 'Analytics (legacy)', icon: BarChart3 },
  { to: '/workflow', label: 'Workflow (legacy)', icon: Kanban, matchPrefixes: ['/workflow', '/pipeline'] },
  { to: '/insights', label: 'Insights (legacy)', icon: Sparkles },
  { to: '/empty', label: 'Empty state', icon: Layers },
];

function isNavActive(pathname: string, to: string, prefixes?: string[]): boolean {
  if (pathname === to) return true;
  if (to === '/dashboard' && pathname === '/') return true;
  if (prefixes) return prefixes.some(p => pathname === p || pathname.startsWith(p + '/'));
  return false;
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-3 text-[10.5px] font-semibold tracking-[0.1em] text-industrial-muted uppercase">
      {children}
    </div>
  );
}

function SidebarLink({
  to,
  icon: Icon,
  label,
  active,
  collapsed = false,
  onClick,
}: {
  to: string;
  icon: typeof Home;
  label: string;
  active: boolean;
  collapsed?: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      title={collapsed ? label : undefined}
      aria-label={collapsed ? label : undefined}
      className={`flex items-center ${collapsed ? 'justify-center px-2 py-2' : 'gap-3 px-3 py-2'} rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-[var(--color-neutral-900)] text-white'
          : 'text-industrial-secondary hover:bg-[var(--bg-tertiary)] hover:text-industrial'
      }`}
    >
      <Icon size={16} />
      {!collapsed && (
        <>
          <span className="flex-1">{label}</span>
          {active && (
            <span
              aria-hidden="true"
              className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] shrink-0"
            />
          )}
        </>
      )}
    </Link>
  );
}

// Mobile breakpoint hook
function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < 768 : false
  );

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return isMobile;
}

export function AppLayout({ children }: AppLayoutProps) {
  const isMobile = useIsMobile();
  useSetupNotifications();
  // Initialize sidebar state synchronously: open on desktop, closed on mobile
  const [sidebarOpen, setSidebarOpen] = useState(
    () => typeof window !== 'undefined' && window.innerWidth >= 768
  );
  const [sidebarCollapsed, toggleSidebarCollapsed] = useCollapsedPreference(
    SIDEBAR_COLLAPSED_KEY,
    false,
  );
  // Collapsed only applies on desktop; mobile keeps full-drawer behavior.
  const isCollapsed = !isMobile && sidebarCollapsed;
  const [demoOpen, setDemoOpen] = useState(false);
  const { user, logout } = useAuthStore();
  const { clearChat } = useChatStore();
  const connectionStatus = useApiHealth();
  const navigate = useNavigate();
  const location = useLocation();
  const { sessionId: currentSessionId } = useParams<{ sessionId?: string }>();
  const { sessions, isLoading, deleteSession } = useChatSessions();
  usePreferences();

  const handleNewChat = () => {
    clearChat();
    navigate('/chat');
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();
    await deleteSession(sessionId);
    if (sessionId === currentSessionId) {
      navigate('/chat');
    }
  };

  // Prevent body scroll when sidebar is open on mobile
  useEffect(() => {
    if (isMobile && sidebarOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobile, sidebarOpen]);

  // Cmd/Ctrl+\ toggles the desktop sidebar collapse.
  useEffect(() => {
    if (isMobile) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === '\\') {
        e.preventDefault();
        toggleSidebarCollapsed();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isMobile, toggleSidebarCollapsed]);

  return (
    <div className="app-shell h-screen flex bg-[var(--bg-primary)]">
      {/* Skip link for keyboard users */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 rounded-lg bg-[var(--accent)] text-[var(--color-neutral-900)] font-medium"
      >
        Skip to main content
      </a>

      {/* Mobile Backdrop */}
      {isMobile && sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/35 backdrop-blur-sm transition-opacity duration-300"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <div
        className={`
          ${isMobile
            ? `fixed inset-y-0 left-0 z-50 w-72 transform transition-transform duration-300 ease-out ${
                sidebarOpen ? 'translate-x-0' : '-translate-x-full'
              }`
            : `${sidebarOpen ? (isCollapsed ? 'w-16' : 'w-72') : 'w-0'} transition-all duration-300`
          }
          app-sidebar flex flex-col border-r border-[var(--border-subtle)] overflow-hidden
        `}
      >
        {/* Sidebar Header — Space Goose logo + wordmark + collapse toggle */}
        <div
          className={`flex items-center ${isCollapsed ? 'flex-col gap-1 px-2' : 'gap-2.5 px-4'} py-4 border-b border-[var(--border-subtle)]`}
        >
          <Link
            to="/dashboard"
            onClick={() => isMobile && setSidebarOpen(false)}
            title={isCollapsed ? 'Space Goose' : undefined}
            className={`flex items-center ${isCollapsed ? 'justify-center' : 'gap-2.5 flex-1 min-w-0'} hover:opacity-80 transition-opacity`}
          >
            <img
              src="/spacegoose-logo.png"
              alt="Space Goose"
              width={isCollapsed ? 36 : 44}
              height={isCollapsed ? 36 : 44}
              className="rounded-full object-cover shrink-0"
            />
            {!isCollapsed && (
              <span className="font-display font-bold text-[20px] text-industrial tracking-[0.02em]">
                SPACE GOOSE
              </span>
            )}
          </Link>
          {!isMobile && (
            <button
              type="button"
              onClick={toggleSidebarCollapsed}
              title={isCollapsed ? 'Expand sidebar (⌘\\)' : 'Collapse sidebar (⌘\\)'}
              aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              className="p-1.5 rounded-md text-industrial-muted hover:bg-[var(--bg-tertiary)] hover:text-industrial-secondary transition-colors shrink-0"
            >
              {isCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
            </button>
          )}
        </div>

        {/* Workspace section */}
        <div className={`${isCollapsed ? 'px-2' : 'px-3'} pt-3 pb-1`}>
          {!isCollapsed && <SectionLabel>Workspace</SectionLabel>}
          <nav className="space-y-0.5 mt-1">
            {WORKSPACE_NAV.map((item) => (
              <SidebarLink
                key={item.to}
                to={item.to}
                icon={item.icon}
                label={item.label}
                active={isNavActive(location.pathname, item.to, item.matchPrefixes)}
                collapsed={isCollapsed}
                onClick={() => isMobile && setSidebarOpen(false)}
              />
            ))}
          </nav>
        </div>

        {/* Demo screens — dev-only scaffolding for legacy/empty states.
            Production builds hide this entirely. Hidden in collapsed rail. */}
        {import.meta.env.DEV && !isCollapsed && (
          <div className="px-3 pt-3 pb-1">
            <button
              type="button"
              onClick={() => setDemoOpen((v) => !v)}
              aria-expanded={demoOpen}
              aria-controls="demo-screens-nav"
              className="w-full flex items-center gap-1.5 px-3 py-1 text-[10.5px] font-semibold tracking-[0.1em] text-industrial-muted uppercase hover:text-industrial-secondary transition-colors"
            >
              <ChevronRight
                size={11}
                className={`transition-transform duration-200 ${demoOpen ? 'rotate-90' : ''}`}
              />
              <span>Demo screens</span>
            </button>
            {demoOpen && (
              <nav id="demo-screens-nav" className="space-y-0.5 mt-1">
                {DEMO_NAV.map((item) => (
                  <SidebarLink
                    key={item.to}
                    to={item.to}
                    icon={item.icon}
                    label={item.label}
                    active={isNavActive(location.pathname, item.to, item.matchPrefixes)}
                    onClick={() => isMobile && setSidebarOpen(false)}
                  />
                ))}
              </nav>
            )}
          </div>
        )}

        {/* New Chat quick-action */}
        <div className={`${isCollapsed ? 'px-2' : 'px-3'} pt-2 pb-1`}>
          <button
            onClick={() => {
              handleNewChat();
              if (isMobile) setSidebarOpen(false);
            }}
            title={isCollapsed ? 'New chat' : undefined}
            aria-label={isCollapsed ? 'New chat' : undefined}
            className={`w-full flex items-center ${isCollapsed ? 'justify-center px-2 py-2' : 'gap-2 px-3 py-2'} rounded-lg text-sm font-medium text-industrial-secondary border border-dashed border-[var(--border-strong)] hover:border-[var(--accent)] hover:text-industrial hover:bg-[var(--bg-tertiary)] transition-colors`}
          >
            <Plus size={14} />
            {!isCollapsed && <span>New chat</span>}
          </button>
        </div>

        {/* Chat History — header + content only render once there's
            something worth showing. Avoids a permanently-empty "History"
            label + placeholder line eating space on fresh accounts.
            Hidden entirely in collapsed rail — the New Chat button stays
            the single entry point, and expanding reveals history. */}
        <div className={`flex-1 overflow-y-auto ${isCollapsed ? 'px-2' : 'px-3'} py-4 scrollbar-thin`}>
          {isCollapsed ? null : isLoading ? (
            <div className="flex items-center gap-2 px-3 py-4">
              <div className="w-1 h-1 rounded-full bg-[var(--accent)] animate-pulse" />
              <div className="w-1 h-1 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:200ms]" />
              <div className="w-1 h-1 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:400ms]" />
            </div>
          ) : sessions.filter(s => s.message_count > 0).length === 0 ? null : (
            <>
            <p className="text-[11px] font-bold text-industrial-muted uppercase tracking-widest px-3 mb-2">History</p>
            <div className="space-y-0.5">
              {sessions.filter(s => s.message_count > 0).map((session) => (
                <Link
                  key={session.id}
                  to={`/chat/${session.id}`}
                  onClick={() => isMobile && setSidebarOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-all group relative ${
                    session.id === currentSessionId
                      ? 'bg-[var(--bg-tertiary)] text-industrial font-medium'
                      : ''
                  }`}
                >
                  {session.title?.startsWith('Analysis:') ? (
                    <Sparkles size={14} className="text-[var(--accent)] flex-shrink-0" />
                  ) : (
                    <MessageSquare size={14} className="text-industrial-muted flex-shrink-0" />
                  )}
                  <span className="flex-1 truncate text-sm">
                    {session.title || 'New conversation'}
                  </span>
                  <button
                    onClick={(e) => handleDeleteSession(e, session.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-[var(--color-error)]/10 text-industrial-muted hover:text-[var(--color-error)] transition-all"
                    title="Delete"
                  >
                    <X size={12} />
                  </button>
                </Link>
              ))}
            </div>
            </>
          )}
        </div>

        {/* Sidebar Footer */}
        <div className={`${isCollapsed ? 'p-2' : 'p-3'} border-t border-[var(--border-subtle)] space-y-0.5`}>
          {/* Upgrade card — always shown; /pricing handles current-plan state.
              Collapsed rail uses a compact mascot-only button. */}
          {(() => {
            const mascotMap: Record<string, { src: string; label: string }> = {
              '/dashboard':  { src: '/mascots/goose-planner.webp',  label: 'Plan smarter' },
              '/chat':       { src: '/mascots/goose-engineer.webp', label: 'Build faster' },
              '/search':     { src: '/mascots/goose-solar.webp',    label: 'Search deeper' },
              '/properties': { src: '/mascots/goose-planet.webp',   label: 'See further' },
              '/projects':   { src: '/mascots/goose-carriers.webp', label: 'Move deals' },
              '/analytics':  { src: '/mascots/goose-planet.webp',   label: 'See further' },
              '/workflow':   { src: '/mascots/goose-mechanic.webp', label: 'Ship faster' },
              '/insights':   { src: '/mascots/goose-solar.webp',    label: 'Think bigger' },
              '/contacts':   { src: '/mascots/goose-carriers.webp', label: 'Grow your network' },
              '/outreach':   { src: '/mascots/goose-welder.webp',   label: 'Close more' },
              '/settings':   { src: '/mascots/goose-mechanic.webp', label: 'Fine-tune' },
            };
            const match = Object.entries(mascotMap).find(([prefix]) =>
              location.pathname === prefix || location.pathname.startsWith(prefix + '/')
            );
            const mascot = match ? match[1] : { src: '/mascots/goose-launch.webp', label: 'Level up' };
            if (isCollapsed) {
              return (
                <Link
                  to="/pricing"
                  onClick={() => isMobile && setSidebarOpen(false)}
                  title="Upgrade"
                  aria-label="Upgrade"
                  className="flex items-center justify-center mb-2 w-12 h-12 mx-auto rounded-full overflow-hidden border border-[var(--border-subtle)] bg-[var(--bg-cream,var(--bg-tertiary))] hover:shadow-sm transition-shadow"
                >
                  <img
                    src={mascot.src}
                    alt=""
                    aria-hidden="true"
                    className="w-10 h-10 object-contain select-none pointer-events-none"
                    draggable={false}
                  />
                </Link>
              );
            }
            return (
              <Link
                to="/pricing"
                onClick={() => isMobile && setSidebarOpen(false)}
                className="block relative mb-2 rounded-xl overflow-hidden border border-[var(--border-subtle)] bg-[var(--bg-cream,var(--bg-tertiary))] hover:shadow-sm transition-shadow group"
              >
                <img
                  src={mascot.src}
                  alt=""
                  aria-hidden="true"
                  className="absolute -right-3 -bottom-3 w-24 h-24 object-contain select-none pointer-events-none opacity-95"
                  draggable={false}
                />
                <div className="relative z-10 p-4 pr-20">
                  <p className="font-display text-[13px] font-semibold text-industrial leading-tight">
                    Ready for more orbit?
                  </p>
                  <p className="text-[11px] text-industrial-secondary leading-snug mt-1.5">
                    Unlimited chats, imports, and outreach on Pro. {mascot.label}.
                  </p>
                  <span className="inline-flex items-center gap-1 mt-2.5 text-[11px] font-semibold text-[var(--accent)] group-hover:underline">
                    Upgrade →
                  </span>
                </div>
              </Link>
            );
          })()}

          {/* Account footer with presence */}
          {(() => {
            const isConnected = connectionStatus === 'connected';
            const initials =
              (user?.first_name?.[0] ?? '') + (user?.last_name?.[0] ?? '') ||
              user?.email?.[0]?.toUpperCase() ||
              'U';
            const displayName = user?.first_name
              ? `${user.first_name}${user.last_name ? ` ${user.last_name}` : ''}`
              : user?.email ?? '';

            if (isCollapsed) {
              return (
                <div className="flex justify-center py-2">
                  <div className="relative">
                    {user?.avatar_url ? (
                      <img src={user.avatar_url} alt="" className="w-8 h-8 rounded-full object-cover" />
                    ) : (
                      <div
                        className="w-8 h-8 rounded-full flex items-center justify-center text-white font-display text-[11px] font-semibold"
                        style={{ background: 'linear-gradient(135deg, var(--color-orbit), var(--color-mist))' }}
                      >
                        {initials}
                      </div>
                    )}
                    <span
                      className="absolute rounded-full border-2 border-white"
                      style={{
                        right: -1,
                        bottom: -1,
                        width: 10,
                        height: 10,
                        background: isConnected ? '#2F7A3B' : 'var(--color-neutral-400)',
                      }}
                    />
                  </div>
                </div>
              );
            }

            return (
              <div className="flex items-center gap-2.5 px-3 py-2">
                <div className="relative flex-shrink-0">
                  {user?.avatar_url ? (
                    <img src={user.avatar_url} alt="" style={{ width: 34, height: 34 }} className="rounded-full object-cover" />
                  ) : (
                    <div
                      className="rounded-full flex items-center justify-center text-white font-display text-[13px] font-semibold"
                      style={{ width: 34, height: 34, background: 'linear-gradient(135deg, var(--color-orbit), var(--color-mist))' }}
                    >
                      {initials}
                    </div>
                  )}
                  <span
                    className="absolute rounded-full border-2 border-white"
                    style={{
                      right: -1,
                      bottom: -1,
                      width: 10,
                      height: 10,
                      background: isConnected ? '#2F7A3B' : 'var(--color-neutral-400)',
                    }}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-semibold text-industrial truncate">{displayName}</div>
                  <div className="text-[11px] text-industrial-secondary flex items-center gap-1.5">
                    <span
                      className="inline-block rounded-full"
                      style={{
                        width: 6,
                        height: 6,
                        background: isConnected ? '#2F7A3B' : 'var(--color-neutral-400)',
                      }}
                    />
                    {isConnected ? 'Connected' : 'Offline'}
                  </div>
                </div>
                <Link
                  to="/settings"
                  onClick={() => isMobile && setSidebarOpen(false)}
                  className="text-industrial-muted hover:text-industrial-secondary transition-colors"
                  title="Settings"
                >
                  <Settings size={16} />
                </Link>
                <button
                  onClick={async () => {
                    await logout();
                    navigate('/login');
                  }}
                  className="text-industrial-muted hover:text-[var(--color-error)] transition-colors"
                  title="Sign out"
                >
                  <LogOut size={16} />
                </button>
              </div>
            );
          })()}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="app-topbar h-14 flex items-center px-4">
          <div className="flex items-center gap-2">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-2 rounded-lg text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors"
                aria-label="Open sidebar"
              >
                <Menu size={20} />
              </button>
            )}
          </div>
        </header>

        {/* Connector health warning banner */}
        <ConnectorHealthBanner />

        {/* Page Content */}
        <main id="main-content" className="flex-1 overflow-hidden bg-[var(--bg-primary)]">{children}</main>
      </div>
    </div>
  );
}
