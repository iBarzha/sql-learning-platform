import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  AreaChart,
  Area,
  ResponsiveContainer,
} from 'recharts';

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  color: string;
  trend?: number[];
  className?: string;
}

export function StatCard({
  label,
  value,
  subtitle,
  icon: Icon,
  color,
  trend,
  className,
}: StatCardProps) {
  const chartData = trend?.map((v, i) => ({ index: i, value: v }));

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-2xl glass shadow-noble-sm p-5',
        'transition-shadow duration-200 hover:shadow-noble-md',
        className
      )}
    >
      {/* Icon badge */}
      <div className="absolute top-4 right-4">
        <div
          className={cn(
            'flex h-10 w-10 items-center justify-center rounded-full',
            'bg-current/10',
            color
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-col gap-1 pr-14">
        <p className="text-sm text-muted-foreground font-medium">{label}</p>
        <p className="text-2xl font-bold tracking-tight">{value}</p>
        {subtitle && (
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        )}
      </div>

      {/* Sparkline */}
      {chartData && chartData.length > 1 && (
        <div className="absolute bottom-3 right-4 h-10 w-24 opacity-60">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id={`stat-gradient-${label}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="currentColor" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="currentColor" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="value"
                stroke="currentColor"
                strokeWidth={1.5}
                fill={`url(#stat-gradient-${label})`}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
