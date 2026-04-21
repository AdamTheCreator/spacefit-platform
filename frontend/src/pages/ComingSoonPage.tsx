import { Link } from 'react-router-dom';
import { AppLayout } from '../components/Layout/AppLayout';

interface ComingSoonPageProps {
  title: string;
  description: string;
  mascot: 'engineer' | 'mechanic' | 'welder' | 'planet' | 'carriers';
}

// Reusable "coming soon" shell for nav items whose full screens haven't
// been ported yet from the Perigee design bundle. Keeps the sidebar
// structure coherent and on-brand while the real pages ship later.
export function ComingSoonPage({ title, description, mascot }: ComingSoonPageProps) {
  return (
    <AppLayout>
      <div className="h-full flex items-center justify-center px-6">
        <div className="text-center max-w-md">
          <img
            src={`/mascots/goose-${mascot}.webp`}
            alt=""
            aria-hidden="true"
            className="w-32 h-32 mx-auto mb-4 object-contain select-none"
            draggable={false}
          />
          <h1 className="font-display text-2xl font-semibold text-industrial mb-2 tracking-tight">
            {title}
          </h1>
          <p className="text-sm text-industrial-secondary leading-relaxed mb-6">
            {description}
          </p>
          <Link
            to="/dashboard"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-neutral-900)] text-white text-sm font-medium hover:bg-[var(--color-neutral-800)] transition-colors"
          >
            Back to dashboard
          </Link>
        </div>
      </div>
    </AppLayout>
  );
}

export function InsightsPage() {
  return (
    <ComingSoonPage
      title="Insights crew is assembling"
      description="What the Engineer flagged for you today — thesis drift, comp outliers, and expiring opportunities in your markets."
      mascot="welder"
    />
  );
}

export default ComingSoonPage;
