import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { Link, useNavigate, useParams, useLocation } from 'react-router-dom';
import {
  MessageSquare,
  Plus,
  User,
  Settings,
  LogOut,
  Users,
  Key,
  Menu,
  X,
  Kanban,
  Mail,
  HelpCircle,
  Sparkles,
  Shield,
  Home,
  Search as SearchIcon,
  Building2,
  BarChart3,
  Star,
} from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useChatSessions } from '../../hooks/useChatSessions';
import { usePreferences } from '../../hooks/usePreferences';
import { ConnectorHealthBanner } from '../ConnectorHealthBanner';
import { useSetupNotifications } from '../../hooks/useSetupNotifications';

interface AppLayoutProps {
  children: React.ReactNode;
}

// Perigee sidebar nav definitions
type NavItem = {
  to: string;
  label: string;
  icon: typeof Home;
  matchPrefixes?: string[];
};

const WORKSPACE_NAV: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: Home },
  { to: '/chat', label: 'Chat', icon: MessageSquare, matchPrefixes: ['/chat'] },
  { to: '/search', label: 'Search', icon: SearchIcon },
  { to: '/projects', label: 'Properties', icon: Building2, matchPrefixes: ['/projects'] },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/workflow', label: 'Workflow', icon: Kanban, matchPrefixes: ['/workflow', '/pipeline'] },
  { to: '/insights', label: 'Insights', icon: Sparkles },
  { to: '/contacts', label: 'Contacts', icon: Users },
  { to: '/outreach', label: 'Outreach', icon: Mail },
];

const STATES_NAV: NavItem[] = [
  { to: '/onboarding', label: 'Onboarding', icon: Star },
  { to: '/settings', label: 'Settings', icon: Settings },
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
  onClick,
}: {
  to: string;
  icon: typeof Home;
  label: string;
  active: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-[var(--color-neutral-900)] text-white'
          : 'text-industrial-secondary hover:bg-[var(--bg-tertiary)] hover:text-industrial'
      }`}
    >
      <Icon size={16} />
      <span className="flex-1">{label}</span>
      {active && (
        <span
          aria-hidden="true"
          className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] shrink-0"
        />
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
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { user, logout } = useAuthStore();
  const { clearChat, connectionStatus } = useChatStore();
  const navigate = useNavigate();
  const location = useLocation();
  const { sessionId: currentSessionId } = useParams<{ sessionId?: string }>();
  const { sessions, isLoading, deleteSession } = useChatSessions();
  usePreferences();

  const handleLogout = useCallback(async () => {
    await logout();
    navigate('/login');
  }, [logout, navigate]);

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

  const menuItems = useMemo(() => [
    { path: '/profile', label: 'Profile' },
    { path: '/contacts', label: 'Contacts' },
    { path: '/connections', label: 'Data Library' },
    { path: '/settings', label: 'Settings' },
    { action: 'logout', label: 'Sign out' },
  ], []);

  const handleDropdownKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!dropdownOpen) return;

    switch (e.key) {
      case 'Escape':
        setDropdownOpen(false);
        setFocusedIndex(-1);
        break;
      case 'ArrowDown':
        e.preventDefault();
        setFocusedIndex(prev => Math.min(prev + 1, menuItems.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setFocusedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (focusedIndex >= 0) {
          const item = menuItems[focusedIndex];
          if (item.action === 'logout') {
            handleLogout();
          } else if (item.path) {
            navigate(item.path);
            setDropdownOpen(false);
          }
        }
        break;
      case 'Tab':
        setDropdownOpen(false);
        setFocusedIndex(-1);
        break;
    }
  }, [dropdownOpen, focusedIndex, menuItems, navigate, handleLogout]);

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
            : `${sidebarOpen ? 'w-72' : 'w-0'} transition-all duration-300`
          }
          app-sidebar flex flex-col border-r border-[var(--border-subtle)] overflow-hidden
        `}
      >
        {/* Sidebar Header — Perigee logo + wordmark */}
        <Link
          to="/dashboard"
          onClick={() => isMobile && setSidebarOpen(false)}
          className="flex items-center gap-2.5 px-4 py-4 border-b border-[var(--border-subtle)] hover:bg-[var(--bg-tertiary)]/40 transition-colors"
        >
          <img
            src="/perigee-logo.png"
            alt="Perigee"
            width={32}
            height={32}
            className="rounded-full object-cover shrink-0"
          />
          <span className="font-display font-bold text-[17px] text-industrial tracking-[0.02em]">
            PERIGEE
          </span>
          <span className="ml-auto inline-flex items-center px-2 py-0.5 rounded-full bg-[var(--bg-tertiary)] text-[10px] font-medium text-industrial-secondary">
            v{import.meta.env.VITE_APP_VERSION ?? '2.4'}
          </span>
        </Link>

        {/* Workspace section */}
        <div className="px-3 pt-3 pb-1">
          <SectionLabel>Workspace</SectionLabel>
          <nav className="space-y-0.5 mt-1">
            {WORKSPACE_NAV.map((item) => (
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
        </div>

        {/* States section */}
        <div className="px-3 pt-3 pb-1">
          <SectionLabel>States</SectionLabel>
          <nav className="space-y-0.5 mt-1">
            {STATES_NAV.map((item) => (
              <SidebarLink
                key={item.to}
                to={item.to}
                icon={item.icon}
                label={item.label}
                active={isNavActive(location.pathname, item.to)}
                onClick={() => isMobile && setSidebarOpen(false)}
              />
            ))}
            {user?.is_admin && (
              <SidebarLink
                to="/admin"
                icon={Shield}
                label="Admin"
                active={isNavActive(location.pathname, '/admin')}
                onClick={() => isMobile && setSidebarOpen(false)}
              />
            )}
          </nav>
        </div>

        {/* New Chat quick-action */}
        <div className="px-3 pt-2 pb-1">
          <button
            onClick={() => {
              handleNewChat();
              if (isMobile) setSidebarOpen(false);
            }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-industrial-secondary border border-dashed border-[var(--border-strong)] hover:border-[var(--accent)] hover:text-industrial hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            <Plus size={14} />
            <span>New chat</span>
          </button>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto px-3 py-4 scrollbar-thin">
          <p className="text-[11px] font-bold text-industrial-muted uppercase tracking-widest px-3 mb-2">History</p>
          {isLoading ? (
            <div className="flex items-center gap-2 px-3 py-4">
              <div className="w-1 h-1 rounded-full bg-[var(--accent)] animate-pulse" />
              <div className="w-1 h-1 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:200ms]" />
              <div className="w-1 h-1 rounded-full bg-[var(--accent)] animate-pulse [animation-delay:400ms]" />
            </div>
          ) : sessions.filter(s => s.message_count > 0).length === 0 ? (
            <div className="text-industrial-muted text-xs px-3 py-4">
              Your conversations will appear here
            </div>
          ) : (
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
          )}
        </div>

        {/* Sidebar Footer */}
        <div className="p-3 border-t border-[var(--border-subtle)] space-y-0.5">
          {/* Upgrade card — always shown; /pricing handles current-plan state */}
          <Link
            to="/pricing"
            onClick={() => isMobile && setSidebarOpen(false)}
            className="block relative mb-2 rounded-xl overflow-hidden border border-[var(--border-subtle)] bg-[var(--bg-cream,var(--bg-tertiary))] hover:shadow-sm transition-shadow group"
          >
            <img
              src="/mascots/goose-solar.webp"
              alt=""
              aria-hidden="true"
              className="absolute -right-3 -bottom-3 w-24 h-24 object-contain select-none pointer-events-none opacity-95"
              draggable={false}
            />
            <div className="relative z-10 p-3 pr-16 max-w-[160px]">
              <p className="font-display text-[12px] font-semibold text-industrial leading-tight">
                Ready for more orbit?
              </p>
              <p className="text-[11px] text-industrial-secondary leading-snug mt-1">
                Unlimited chats, imports, and outreach on Pro.
              </p>
              <span className="inline-flex items-center gap-1 mt-2 text-[11px] font-semibold text-[var(--accent)] group-hover:underline">
                Upgrade →
              </span>
            </div>
          </Link>

          <a
            href="mailto:support-perigee@agentmail.to"
            className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors"
          >
            <HelpCircle size={16} />
            <span>Support</span>
          </a>
          <div className="px-3 pt-2">
             <p className="text-[10px] text-industrial-muted">Perigee v{import.meta.env.VITE_APP_VERSION}</p>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="app-topbar h-14 flex items-center justify-between px-4">
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
            <span
              className={`ml-2 inline-flex items-center gap-1.5 text-[11px] font-medium text-industrial-muted ${
                connectionStatus === 'connected' ? '' : 'text-industrial-secondary'
              }`}
              title={
                connectionStatus === 'connected'
                  ? 'Connected to server'
                  : connectionStatus === 'connecting'
                  ? 'Connecting to server'
                  : 'Disconnected from server'
              }
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  connectionStatus === 'connected'
                    ? 'bg-emerald-500 animate-pulse-slow'
                    : connectionStatus === 'connecting'
                    ? 'bg-amber-500 animate-pulse-slow'
                    : 'bg-red-500'
                }`}
              />
              <span className="hidden sm:inline">
                {connectionStatus === 'connected'
                  ? 'Connected'
                  : connectionStatus === 'connecting'
                  ? 'Connecting…'
                  : 'Offline'}
              </span>
            </span>
          </div>

          <div className="flex items-center gap-3">
            {/* User Dropdown */}
            <div className="relative" ref={dropdownRef} onKeyDown={handleDropdownKeyDown}>
            <button
              onClick={() => {
                setDropdownOpen(prev => !prev);
                setFocusedIndex(dropdownOpen ? -1 : 0);
              }}
              className="flex items-center gap-2 p-1 rounded-full hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-[var(--accent-subtle)] text-[var(--accent)] flex items-center justify-center font-bold text-xs">
                {user?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || 'U'}
              </div>
            </button>

            {dropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setDropdownOpen(false)}
                />
                <div
                  className="absolute right-0 mt-2 w-56 bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-2xl shadow-md z-20 overflow-hidden animate-scale-in"
                  role="menu"
                  aria-orientation="vertical"
                >
                  <div className="px-4 py-3 border-b border-[var(--border-subtle)] bg-[var(--bg-tertiary)]">
                    <p className="text-sm font-medium text-industrial">
                      {user?.first_name} {user?.last_name}
                    </p>
                    <p className="text-xs text-industrial-muted mt-0.5">{user?.email}</p>
                  </div>

                  <div className="py-1">
                    <Link
                      to="/profile"
                      onClick={() => setDropdownOpen(false)}
                      className={`flex items-center gap-3 px-4 py-2.5 text-sm text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors ${focusedIndex === 0 ? 'bg-[var(--bg-tertiary)]' : ''}`}
                      role="menuitem"
                      tabIndex={focusedIndex === 0 ? 0 : -1}
                    >
                      <User size={16} />
                      <span>Profile</span>
                    </Link>

                  <Link
                    to="/customers"
                    onClick={() => setDropdownOpen(false)}
                    className={`flex items-center gap-3 px-4 py-2.5 text-sm text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors ${focusedIndex === 1 ? 'bg-[var(--bg-tertiary)]' : ''}`}
                    role="menuitem"
                    tabIndex={focusedIndex === 1 ? 0 : -1}
                  >
                    <Users size={16} />
                    <span>Customers</span>
                  </Link>

                  <Link
                    to="/connections"
                    onClick={() => setDropdownOpen(false)}
                    className={`flex items-center gap-3 px-4 py-2.5 text-sm text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors ${focusedIndex === 2 ? 'bg-[var(--bg-tertiary)]' : ''}`}
                    role="menuitem"
                    tabIndex={focusedIndex === 2 ? 0 : -1}
                  >
                    <Key size={16} />
                    <span>Data Library</span>
                  </Link>

                  <Link
                    to="/settings"
                    onClick={() => setDropdownOpen(false)}
                    className={`flex items-center gap-3 px-4 py-2.5 text-sm text-industrial-secondary hover:bg-[var(--bg-tertiary)] transition-colors ${focusedIndex === 3 ? 'bg-[var(--bg-tertiary)]' : ''}`}
                    role="menuitem"
                    tabIndex={focusedIndex === 3 ? 0 : -1}
                  >
                      <Settings size={16} />
                      <span>Settings</span>
                    </Link>
                  </div>

                  <div className="border-t border-[var(--border-subtle)] py-1">
                    <button
                      onClick={() => { setDropdownOpen(false); handleLogout(); }}
                      role="menuitem"
                      tabIndex={focusedIndex === 4 ? 0 : -1}
                      className={`flex items-center gap-3 px-4 py-2.5 text-sm text-[var(--color-error)] hover:bg-[var(--bg-error)] transition-colors w-full ${focusedIndex === 4 ? 'bg-[var(--bg-error)]' : ''}`}
                    >
                      <LogOut size={16} />
                      <span>Sign out</span>
                    </button>
                  </div>
                </div>
              </>
            )}
            </div>
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
