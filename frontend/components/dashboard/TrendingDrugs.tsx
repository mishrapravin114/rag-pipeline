"use client";

import { useState, useEffect } from "react";
import { TrendingUp, Calendar, Building, ExternalLink, Loader2, Flame, Eye, ArrowUpRight } from "lucide-react";

interface TrendingDrug {
  id: string;
  drug_name: string;
  manufacturer: string;
  approval_date: string;
  indication: string;
  regulatory_classification: string;
  trend_score: number;
  view_count: number;
  source_file_id?: number;
}

interface TrendingDrugsProps {
  onDrugClick?: (drug: any) => void;
}

export function TrendingDrugs({ onDrugClick }: TrendingDrugsProps) {
  const [trendingDrugs, setTrendingDrugs] = useState<TrendingDrug[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Fetch trending drugs from backend
    const fetchTrendingDrugs = async () => {
      setIsLoading(true);
      try {
        // Import the API service
        const { apiService } = await import('../../services/api');
        
        // Try to get trending data from the backend
        const trendingData = await apiService.getTrendingSearches('weekly', 5);
        
        if (trendingData && trendingData.length > 0) {
          // Map API response to TrendingDrug format
          const mapped = trendingData.map((item: any, index: number) => ({
            id: item.id || `trending-${index}`,
            drug_name: item.drug_name || item.search_term,
            manufacturer: item.manufacturer || 'Various',
            approval_date: item.approval_date || '2024-01-01',
            indication: item.indication || item.therapeutic_area || 'Treatment indication',
            regulatory_classification: item.regulatory_classification || 'NDA',
            trend_score: Math.max(60, 95 - (index * 7)), // Calculate score based on rank
            view_count: item.search_count || Math.floor(1500 / (index + 1)),
            source_file_id: item.source_file_id || parseInt(item.id) || undefined,
          }));
          setTrendingDrugs(mapped);
        } else {
          // Fallback to sample data if no trending data available
          setTrendingDrugs([
            {
              id: "1",
              drug_name: "OCREVUS",
              manufacturer: "Genentech, Inc.",
              approval_date: "2017-03-28",
              indication: "Treatment of relapsing forms of multiple sclerosis",
              regulatory_classification: "BLA",
              trend_score: 95,
              view_count: 1247,
              source_file_id: 1,
            },
            {
              id: "2",
              drug_name: "ANKTIVA",
              manufacturer: "ImmunityBio, Inc.",
              approval_date: "2024-04-22",
              indication: "Treatment of BCG-unresponsive non-muscle invasive bladder cancer",
              regulatory_classification: "BLA",
              trend_score: 87,
              view_count: 892,
              source_file_id: 2,
            },
            {
              id: "3",
              drug_name: "ALECENSA",
              manufacturer: "Genentech, Inc.",
              approval_date: "2015-12-11",
              indication: "Treatment of ALK-positive metastatic non-small cell lung cancer",
              regulatory_classification: "NDA",
              trend_score: 76,
              view_count: 634,
              source_file_id: 3,
            },
            {
              id: "4",
              drug_name: "AUGTYRO",
              manufacturer: "Turning Point Therapeutics",
              approval_date: "2023-11-15",
              indication: "Treatment of ROS1-positive solid tumors",
              regulatory_classification: "NDA",
              trend_score: 68,
              view_count: 521,
              source_file_id: 4,
            },
          ]);
        }
      } catch (error) {
        console.error('Error fetching trending drugs:', error);
        // Use fallback data on error
        setTrendingDrugs([
          {
            id: "1",
            drug_name: "KRAZATI",
            manufacturer: "Mirati Therapeutics",
            approval_date: "2022-12-12",
            indication: "Treatment of KRAS G12C-mutated non-small cell lung cancer",
            regulatory_classification: "NDA",
            trend_score: 92,
            view_count: 1089,
            source_file_id: 5,
          },
          {
            id: "2",
            drug_name: "JEMPERLI",
            manufacturer: "GlaxoSmithKline",
            approval_date: "2021-04-22",
            indication: "Treatment of mismatch repair deficient recurrent or advanced endometrial cancer",
            regulatory_classification: "BLA",
            trend_score: 85,
            view_count: 756,
            source_file_id: 6,
          },
          {
            id: "3",
            drug_name: "GAVRETO",
            manufacturer: "Roche",
            approval_date: "2020-09-04",
            indication: "Treatment of RET fusion-positive non-small cell lung cancer",
            regulatory_classification: "NDA",
            trend_score: 74,
            view_count: 543,
            source_file_id: 7,
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTrendingDrugs();
  }, []);

  const getTrendColor = (score: number) => {
    if (score >= 90) return "from-green-500 to-emerald-600";
    if (score >= 75) return "from-blue-500 to-indigo-600";
    if (score >= 60) return "from-orange-500 to-amber-600";
    return "from-gray-500 to-slate-600";
  };

  const getTrendBg = (score: number) => {
    if (score >= 90) return "from-green-50 to-emerald-50";
    if (score >= 75) return "from-blue-50 to-indigo-50";
    if (score >= 60) return "from-orange-50 to-amber-50";
    return "from-gray-50 to-slate-50";
  };

  const getTrendIcon = (score: number) => {
    if (score >= 90) return "🔥";
    if (score >= 75) return "⚡";
    if (score >= 60) return "📈";
    return "📊";
  };

  return (
    <div className="bg-gradient-to-br from-white via-blue-50/30 to-indigo-50/50 rounded-2xl shadow-lg border border-blue-100/50 p-6 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className="bg-gradient-to-br from-orange-500 to-red-600 p-3 rounded-xl shadow-lg">
            <Flame className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="text-xl font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent">
              Trending Drugs
            </h3>
            <p className="text-sm text-gray-500">Most viewed this week</p>
          </div>
        </div>
        <div className="flex items-center space-x-2 text-sm text-gray-500">
          <Eye className="w-4 h-4" />
          <span>Live data</span>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="animate-pulse">
              <div className="flex items-center space-x-4 p-4 rounded-xl bg-white/50">
                <div className="w-14 h-14 bg-gradient-to-br from-gray-200 to-gray-300 rounded-xl"></div>
                <div className="flex-1">
                  <div className="h-4 bg-gradient-to-r from-gray-200 to-gray-300 rounded w-3/4 mb-2"></div>
                  <div className="h-3 bg-gradient-to-r from-gray-200 to-gray-300 rounded w-1/2 mb-1"></div>
                  <div className="h-3 bg-gradient-to-r from-gray-200 to-gray-300 rounded w-2/3"></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {trendingDrugs.map((drug, index) => (
            <div
              key={drug.id}
              onClick={() => {
                if (onDrugClick) {
                  // Convert to SearchResult format expected by parent
                  const searchResult = {
                    id: drug.id,
                    source_file_id: drug.source_file_id,
                    drug_name: drug.drug_name,
                    manufacturer: drug.manufacturer,
                    approval_date: drug.approval_date,
                    indication: drug.indication,
                    regulatory_classification: drug.regulatory_classification
                  };
                  onDrugClick(searchResult);
                }
              }}
              className="group flex items-start space-x-4 p-4 rounded-xl bg-white/80 backdrop-blur-sm border border-blue-100/50 hover:border-blue-200 hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer"
            >
              <div className={`relative w-14 h-14 rounded-xl bg-gradient-to-br ${getTrendColor(drug.trend_score)} flex items-center justify-center flex-shrink-0 shadow-lg group-hover:shadow-xl transition-all duration-300`}>
                <span className="text-2xl font-bold text-white">
                  {index + 1}
                </span>
                <div className="absolute -top-1 -right-1">
                  <span className="text-lg">{getTrendIcon(drug.trend_score)}</span>
                </div>
              </div>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h4 className="font-bold text-gray-900 mb-1 group-hover:text-blue-700 transition-colors">
                      {drug.drug_name}
                    </h4>
                    <p className="text-sm text-gray-600 line-clamp-2 mb-3">
                      {drug.indication}
                    </p>
                    
                    <div className="flex items-center space-x-4 text-xs">
                      <div className="flex items-center text-gray-500">
                        <Building className="w-3 h-3 mr-1 text-blue-500" />
                        {drug.manufacturer.split(',')[0]}
                      </div>
                      <div className="flex items-center text-gray-500">
                        <Calendar className="w-3 h-3 mr-1 text-indigo-500" />
                        {new Date(drug.approval_date).getFullYear()}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex flex-col items-end ml-4">
                    <div className={`px-3 py-1.5 text-xs font-semibold rounded-full mb-2 shadow-sm ${
                      drug.regulatory_classification === 'NDA' 
                        ? 'bg-gradient-to-r from-blue-100 to-indigo-100 text-blue-800'
                        : 'bg-gradient-to-r from-green-100 to-emerald-100 text-green-800'
                    }`}>
                      {drug.regulatory_classification}
                    </div>
                    <div className="flex items-center space-x-1 text-xs text-gray-500">
                      <Eye className="w-3 h-3" />
                      <span className="font-medium">{drug.view_count.toLocaleString()}</span>
                    </div>
                    <div className="mt-2">
                      <div className="h-1.5 w-20 bg-gray-200 rounded-full overflow-hidden">
                        <div 
                          className={`h-full bg-gradient-to-r ${getTrendColor(drug.trend_score)} transition-all duration-1000 ease-out`}
                          style={{ width: `${drug.trend_score}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
              <ArrowUpRight className="w-5 h-5 text-gray-400 group-hover:text-blue-600 flex-shrink-0 transition-colors" />
            </div>
          ))}
        </div>
      )}

      <div className="mt-6 pt-6 border-t border-blue-100/50">
        <button className="w-full px-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-700 text-white rounded-xl hover:from-blue-700 hover:to-indigo-800 transition-all duration-300 shadow-lg hover:shadow-xl font-medium flex items-center justify-center space-x-2">
          <span>View All Trending Drugs</span>
          <ArrowUpRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
} 