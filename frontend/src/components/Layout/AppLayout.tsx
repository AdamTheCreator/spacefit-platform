import { useState, useCallback, useEffect, useRef } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  MessageSquare,
  Plus,
  User,
  Settings,
  LogOut,
  Users,
  Key,
  ChevronDown,
  Menu,
  X,
  Kanban,
  FileText,
  Mail,
  Sparkles,
  HelpCircle,
} from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useChatSessions } from '../../hooks/useChatSessions';
import { usePreferences } from '../../hooks/usePreferences';
import { ConnectorHealthBanner } from '../ConnectorHealthBanner';

interface AppLayoutProps {
  children: React.ReactNode;
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
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Open sidebar by default on desktop only, after mount
  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth >= 768) {
      setSidebarOpen(true);
    }
  }, []);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { user, logout } = useAuthStore();
  const { clearChat } = useChatStore();
  const navigate = useNavigate();
  const { sessionId: currentSessionId } = useParams<{ sessionId?: string }>();
  const { sessions, isLoading, deleteSession } = useChatSessions();
  const { data: preferences } = usePreferences();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

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

  const menuItems = [
    { path: '/profile', label: 'Profile' },
    { path: '/customers', label: 'Customers' },
    { path: '/connections', label: 'Connections' },
    { path: '/settings', label: 'Settings' },
    { action: 'logout', label: 'Sign out' },
  ];

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

  useEffect(() => {
    if (dropdownOpen) {
      setFocusedIndex(0);
    } else {
      setFocusedIndex(-1);
    }
  }, [dropdownOpen]);

  // Close sidebar on mobile when navigating
  useEffect(() => {
    if (isMobile) {
      setSidebarOpen(false);
    }
  }, [currentSessionId, isMobile]);

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
    <div className="h-screen flex bg-[var(--bg-primary)] dark">
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
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity duration-300"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <div
        className={`
          ${isMobile
            ? `fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-300 ease-out ${
                sidebarOpen ? 'translate-x-0' : '-translate-x-full'
              }`
            : `${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-300`
          }
          flex flex-col bg-[var(--bg-secondary)] border-r border-[var(--border-subtle)] overflow-hidden
        `}
      >
        {/* Sidebar Header */}
        <div className="p-4 border-b border-[var(--border-subtle)]">
          <div className="flex items-center justify-between gap-2">
            <button
              onClick={() => {
                handleNewChat();
                if (isMobile) setSidebarOpen(false);
              }}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--accent)] text-[var(--color-neutral-900)] font-medium text-sm hover:bg-[var(--accent-hover)] transition-colors shadow-sm min-h-[44px]"
            >
              <Plus size={16} />
              New Chat
            </button>
            {/* Mobile close button */}
            {isMobile && (
              <button
                onClick={() => setSidebarOpen(false)}
                className="p-2.5 rounded-lg text-industrial-secondary hover:text-industrial hover:bg-[var(--hover-overlay)] transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
                aria-label="Close sidebar"
              >
                <X size={20} />
              </button>
            )}
          </div>
        </div>

        {/* Main Navigation */}
        <div className="p-3 border-b border-[var(--border-subtle)]">
          <p className="text-[11px] font-medium text-industrial-muted uppercase tracking-wide px-3 py-2">Navigation</p>
          <nav className="space-y-1">
            <Link
              to="/pipeline"
              onClick={() => isMobile && setSidebarOpen(false)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-industrial-secondary hover:text-industrial hover:bg-[var(--hover-overlay)] transition-colors min-h-[44px]"
            >
              <Kanban size={16} />
              <span>Pipeline</span>
            </Link>
            <Link
              to="/documents"
              onClick={() => isMobile && setSidebarOpen(false)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-industrial-secondary hover:text-industrial hover:bg-[var(--hover-overlay)] transition-colors min-h-[44px]"
            >
              <FileText size={16} />
              <span>Documents</span>
            </Link>
            <Link
              to="/outreach"
              onClick={() => isMobile && setSidebarOpen(false)}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-industrial-secondary hover:text-industrial hover:bg-[var(--hover-overlay)] transition-colors min-h-[44px]"
            >
              <Mail size={16} />
              <span>Outreach</span>
            </Link>
          </nav>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto p-3 scrollbar-thin">
          <p className="text-[11px] font-medium text-industrial-muted uppercase tracking-wide px-3 py-2">Conversations</p>
          {isLoading ? (
            <div className="text-industrial-muted text-sm px-3 py-4">Loading...</div>
          ) : sessions.filter(s => s.message_count > 0).length === 0 ? (
            <div className="text-industrial-muted text-sm px-3 py-4">
              No conversations yet
            </div>
          ) : (
            <div className="space-y-1">
              {sessions.filter(s => s.message_count > 0).map((session) => (
                <Link
                  key={session.id}
                  to={`/chat/${session.id}`}
                  onClick={() => isMobile && setSidebarOpen(false)}
                  className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-industrial-secondary hover:bg-[var(--hover-overlay)] transition-all group min-h-[44px] ${
                    session.id === currentSessionId
                      ? 'bg-[var(--accent-subtle)] text-industrial border-l-2 border-[var(--accent)] rounded-l-none'
                      : ''
                  }`}
                >
                  <MessageSquare size={14} className="text-industrial-muted flex-shrink-0" />
                  <span className="flex-1 truncate text-sm">
                    {session.title || 'New conversation'}
                  </span>
                  <button
                    onClick={(e) => handleDeleteSession(e, session.id)}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-md hover:bg-[var(--bg-error)] transition-all"
                    title="Delete conversation"
                    aria-label="Delete conversation"
                  >
                    <X size={12} className="text-industrial-muted group-hover:text-[var(--color-error)]" />
                  </button>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-[var(--border-subtle)] space-y-3">
          {/* Profile Completion Nudge */}
          {preferences && !preferences.is_complete && (
            <Link
              to="/settings"
              className="block p-3 rounded-lg bg-[var(--accent-subtle)] hover:bg-[var(--accent)]/20 transition-colors group"
            >
              <div className="flex items-center gap-2 mb-2">
                <Sparkles size={14} className="text-[var(--accent)]" />
                <span className="text-xs font-medium text-[var(--accent)]">Complete Setup</span>
              </div>
              <div className="h-1.5 bg-[var(--bg-primary)] rounded-full overflow-hidden mb-2">
                <div
                  className="h-full bg-[var(--accent)] rounded-full transition-all"
                  style={{ width: `${preferences.completion_percentage}%` }}
                />
              </div>
              <p className="text-xs text-industrial-muted group-hover:text-industrial-secondary">
                {preferences.completion_percentage}% complete
              </p>
            </Link>
          )}
          <a
            href="mailto:support-spacefit@agentmail.to"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-industrial-secondary hover:text-industrial hover:bg-[var(--hover-overlay)] transition-colors min-h-[44px]"
          >
            <HelpCircle size={16} />
            <span>Support</span>
          </a>
          <p className="text-[11px] text-industrial-muted px-1">SpaceFit v{import.meta.env.VITE_APP_VERSION}</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="h-14 min-h-[48px] flex items-center justify-between px-2 sm:px-4 border-b border-[var(--border-subtle)] bg-[var(--bg-secondary)]">
          <div className="flex items-center gap-2 sm:gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
              className="p-2.5 rounded-lg text-industrial-secondary hover:text-industrial hover:bg-[var(--hover-overlay)] transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
            >
              <Menu size={20} />
            </button>
            {/* Logo - centered on mobile */}
            <div className="flex items-center gap-2.5">
              <div className="w-2 h-2 rounded-sm bg-[var(--accent)]" />
              <span className="text-sm font-semibold tracking-wide text-industrial">
                SpaceFit
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1 sm:gap-2">
            {/* New Chat button - mobile only (icon only) */}
            {isMobile && (
              <button
                onClick={handleNewChat}
                aria-label="New chat"
                className="p-2.5 rounded-lg bg-[var(--accent)] text-[var(--color-neutral-900)] hover:bg-[var(--accent-hover)] transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center"
              >
                <Plus size={18} />
              </button>
            )}

            {/* User Dropdown */}
            <div className="relative" ref={dropdownRef} onKeyDown={handleDropdownKeyDown}>
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              aria-haspopup="menu"
              aria-expanded={dropdownOpen}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-industrial-secondary hover:bg-[var(--hover-overlay)] transition-colors min-h-[44px]"
            >
              <div className="w-8 h-8 rounded-full bg-[var(--accent)] flex items-center justify-center flex-shrink-0">
                <span className="text-[var(--color-neutral-900)] text-sm font-semibold">
                  {user?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || 'U'}
                </span>
              </div>
              <span className="text-sm font-medium hidden sm:block">
                {user?.first_name || user?.email?.split('@')[0]}
              </span>
              <ChevronDown size={16} className="text-industrial-muted hidden sm:block" />
            </button>

            {dropdownOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setDropdownOpen(false)}
                />
                <div
                  className="absolute right-0 mt-2 w-56 bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-xl shadow-lg z-20 overflow-hidden animate-scale-in"
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
                      role="menuitem"
                      tabIndex={focusedIndex === 0 ? 0 : -1}
                      className={`flex items-center gap-3 px-4 py-2.5 text-sm text-industrial-secondary hover:bg-[var(--hover-overlay)] transition-colors ${focusedIndex === 0 ? 'bg-[var(--hover-overlay)]' : ''}`}
                    >
                      <User size={16} />
                      <span>Profile</span>
                    </Link>

                    <Link
                      to="/customers"
                      onClick={() => setDropdownOpen(false)}
                      role="menuitem"
                      tabIndex={focusedIndex === 1 ? 0 : -1}
                      className={`flex items-center gap-3 px-4 py-2.5 text-sm text-industrial-secondary hover:bg-[var(--hover-overlay)] transition-colors ${focusedIndex === 1 ? 'bg-[var(--hover-overlay)]' : ''}`}
                    >
                      <Users size={16} />
                      <span>Customers</span>
                    </Link>

                    <Link
                      to="/connections"
                      onClick={() => setDropdownOpen(false)}
                      role="menuitem"
                      tabIndex={focusedIndex === 2 ? 0 : -1}
                      className={`flex items-center gap-3 px-4 py-2.5 text-sm text-industrial-secondary hover:bg-[var(--hover-overlay)] transition-colors ${focusedIndex === 2 ? 'bg-[var(--hover-overlay)]' : ''}`}
                    >
                      <Key size={16} />
                      <span>Connections</span>
                    </Link>

                    <Link
                      to="/settings"
                      onClick={() => setDropdownOpen(false)}
                      role="menuitem"
                      tabIndex={focusedIndex === 3 ? 0 : -1}
                      className={`flex items-center gap-3 px-4 py-2.5 text-sm text-industrial-secondary hover:bg-[var(--hover-overlay)] transition-colors ${focusedIndex === 3 ? 'bg-[var(--hover-overlay)]' : ''}`}
                    >
                      <Settings size={16} />
                      <span>Settings</span>
                    </Link>
                  </div>

                  <div className="border-t border-[var(--border-subtle)] py-1">
                    <button
                      onClick={handleLogout}
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
