"use client";

import { 
  Pill, 
  Building, 
  Calendar, 
  FileText,
  TrendingUp,
  Users,
  Activity,
  Loader2
} from "lucide-react";

interface StatsWidgetProps {
  title: string;
  value: number;
  icon: "pill" | "building" | "calendar" | "document" | "trending" | "users" | "activity";
  color: "blue" | "green" | "purple" | "orange" | "red" | "indigo";
  subtitle?: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  loading?: boolean;
}

const iconMap = {
  pill: Pill,
  building: Building,
  calendar: Calendar,
  document: FileText,
  trending: TrendingUp,
  users: Users,
  activity: Activity,
};

const colorMap = {
  blue: {
    bg: "from-blue-500 to-indigo-600",
    lightBg: "from-blue-50 to-indigo-50",
    icon: "text-white",
    text: "text-gray-900",
    border: "border-blue-100",
  },
  green: {
    bg: "from-green-500 to-emerald-600",
    lightBg: "from-green-50 to-emerald-50",
    icon: "text-white",
    text: "text-gray-900",
    border: "border-green-100",
  },
  purple: {
    bg: "from-purple-500 to-violet-600",
    lightBg: "from-purple-50 to-violet-50",
    icon: "text-white",
    text: "text-gray-900",
    border: "border-purple-100",
  },
  orange: {
    bg: "from-orange-500 to-amber-600",
    lightBg: "from-orange-50 to-amber-50",
    icon: "text-white",
    text: "text-gray-900",
    border: "border-orange-100",
  },
  red: {
    bg: "from-red-500 to-rose-600",
    lightBg: "from-red-50 to-rose-50",
    icon: "text-white",
    text: "text-gray-900",
    border: "border-red-100",
  },
  indigo: {
    bg: "from-indigo-500 to-purple-600",
    lightBg: "from-indigo-50 to-purple-50",
    icon: "text-white",
    text: "text-gray-900",
    border: "border-indigo-100",
  },
};

export function StatsWidget({ 
  title, 
  value, 
  icon, 
  color, 
  subtitle, 
  trend,
  loading = false
}: StatsWidgetProps) {
  const IconComponent = iconMap[icon];
  const colors = colorMap[color];

  return (
    <div className={`bg-gradient-to-br ${colors.lightBg} rounded-2xl shadow-lg border ${colors.border} p-6 hover:shadow-xl transition-all duration-300 backdrop-blur-sm`}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-semibold text-gray-600 mb-2">{title}</p>
          {loading ? (
            <div className="flex items-center space-x-2">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
              <span className="text-sm text-gray-500">Loading...</span>
            </div>
          ) : (
            <>
              <div className="flex items-baseline space-x-2">
                <p className={`text-3xl font-bold ${colors.text}`}>
                  {value.toLocaleString()}
                </p>
                {trend && (
                  <span className={`text-sm font-medium flex items-center ${
                    trend.isPositive ? 'text-green-600' : 'text-red-600'
                  }`}>
                    <TrendingUp className={`w-3 h-3 mr-1 ${trend.isPositive ? '' : 'rotate-180'}`} />
                    {trend.isPositive ? '+' : ''}{trend.value}%
                  </span>
                )}
              </div>
              {subtitle && (
                <p className="text-xs text-gray-500 mt-2 font-medium">{subtitle}</p>
              )}
            </>
          )}
        </div>
        <div className={`bg-gradient-to-br ${colors.bg} p-4 rounded-xl shadow-lg`}>
          <IconComponent className={`w-7 h-7 ${colors.icon}`} />
        </div>
      </div>
      
      {/* Progress bar for visual appeal */}
      {!loading && value > 0 && (
        <div className="mt-4">
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className={`h-full bg-gradient-to-r ${colors.bg} transition-all duration-1000 ease-out`}
              style={{ width: `${Math.min((value / 100) * 100, 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}