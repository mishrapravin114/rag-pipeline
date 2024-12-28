"use client";

import { Search, FileText, BarChart3, Upload, Download, Settings, Sparkles, ArrowRight } from "lucide-react";

interface QuickActionsProps {
  onActionClick: (action: string) => void;
}

const actions = [
  {
    id: "advanced-search",
    title: "Advanced Search",
    description: "Search with filters and criteria",
    icon: Search,
    color: "blue",
  },
  {
    id: "generate-report",
    title: "Generate Report",
    description: "Create analysis reports",
    icon: FileText,
    color: "green",
  },
  {
    id: "view-analytics",
    title: "View Analytics",
    description: "Dashboard insights and trends",
    icon: BarChart3,
    color: "purple",
  },
  {
    id: "upload-documents",
    title: "Upload Documents",
    description: "Add new FDA documents",
    icon: Upload,
    color: "orange",
  },
  {
    id: "export-data",
    title: "Export Data",
    description: "Download search results",
    icon: Download,
    color: "indigo",
  },
  {
    id: "settings",
    title: "Settings",
    description: "Configure preferences",
    icon: Settings,
    color: "gray",
  },
];

const colorMap = {
  blue: {
    gradient: "from-blue-500 to-indigo-600",
    bg: "from-blue-50 to-indigo-50",
    hover: "hover:from-blue-100 hover:to-indigo-100",
    text: "text-blue-700",
    border: "border-blue-100"
  },
  green: {
    gradient: "from-green-500 to-emerald-600",
    bg: "from-green-50 to-emerald-50",
    hover: "hover:from-green-100 hover:to-emerald-100",
    text: "text-green-700",
    border: "border-green-100"
  },
  purple: {
    gradient: "from-purple-500 to-violet-600",
    bg: "from-purple-50 to-violet-50",
    hover: "hover:from-purple-100 hover:to-violet-100",
    text: "text-purple-700",
    border: "border-purple-100"
  },
  orange: {
    gradient: "from-orange-500 to-amber-600",
    bg: "from-orange-50 to-amber-50",
    hover: "hover:from-orange-100 hover:to-amber-100",
    text: "text-orange-700",
    border: "border-orange-100"
  },
  indigo: {
    gradient: "from-indigo-500 to-purple-600",
    bg: "from-indigo-50 to-purple-50",
    hover: "hover:from-indigo-100 hover:to-purple-100",
    text: "text-indigo-700",
    border: "border-indigo-100"
  },
  gray: {
    gradient: "from-gray-500 to-slate-600",
    bg: "from-gray-50 to-slate-50",
    hover: "hover:from-gray-100 hover:to-slate-100",
    text: "text-gray-700",
    border: "border-gray-100"
  },
};

export function QuickActions({ onActionClick }: QuickActionsProps) {
  return (
    <div className="bg-gradient-to-br from-white via-blue-50/30 to-indigo-50/50 rounded-2xl shadow-lg border border-blue-100/50 p-6 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className="bg-gradient-to-br from-indigo-500 to-purple-600 p-3 rounded-xl shadow-lg">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="text-xl font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent">
              Quick Actions
            </h3>
            <p className="text-sm text-gray-500">Frequently used features</p>
          </div>
        </div>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {actions.map((action) => {
          const IconComponent = action.icon;
          const colors = colorMap[action.color as keyof typeof colorMap];
          
          return (
            <button
              key={action.id}
              onClick={() => onActionClick(action.id)}
              className={`group relative p-5 rounded-xl bg-gradient-to-br ${colors.bg} border ${colors.border} ${colors.hover} hover:shadow-xl hover:scale-[1.03] transition-all duration-300 text-left overflow-hidden`}
            >
              <div className="absolute inset-0 bg-gradient-to-br from-white/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <div className="relative z-10">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${colors.gradient} flex items-center justify-center mb-3 shadow-lg group-hover:shadow-xl transition-all duration-300 group-hover:scale-110`}>
                  <IconComponent className="w-6 h-6 text-white" />
                </div>
                <h4 className={`font-bold ${colors.text} mb-1 group-hover:translate-x-0.5 transition-transform flex items-center justify-between`}>
                  {action.title}
                  <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-all duration-300" />
                </h4>
                <p className="text-sm text-gray-600">
                  {action.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
} 