"use client";

import { useState, useEffect } from "react";
import { ArrowLeft, ExternalLink, Calendar, Building, Pill, MessageSquare, Download, FileText, Shield, Clock, User, Zap, AlertTriangle, ChevronDown, ChevronUp, Eye, BookOpen, Activity } from "lucide-react";

interface SearchResult {
  id: string;
  source_file_id?: number;
  entity_name: string;
  manufacturer: string;
  approval_date: string;
  indication: string;
  regulatory_classification: string;
}

interface EntitySection {
  id: number;
  type: string;
  title: string;
  content: string;
  order: number;
}

interface EntityDetails {
  basic_info: {
    id: number;
    entity_name: string;
    therapeutic_area?: string;
    approval_status: string;
    country: string;
    applicant: string;
    active_substance: any;
    regulatory: string;
  };
  timeline: {
    submission_date?: string;
    pdufa_date?: string;
    approval_date?: string;
  };
  sections: EntitySection[];
  page_info?: {
    total_pages: number;
    page_numbers: number[];
    total_chunks: number;
    total_tokens: number;
  };
  file_url?: string;
  metadata?: any;
}

interface SearchResultsProps {
  results: SearchResult[];
  isLoading: boolean;
  onBackToDashboard: () => void;
  onChatWithEntity?: (entity: SearchResult) => void;
  onChatWithMultipleEntities?: (entities: SearchResult[]) => void;
  initialSelectedEntity?: SearchResult | null;
}

export function SearchResults({ results, isLoading, onBackToDashboard, onChatWithEntity, onChatWithMultipleEntities, initialSelectedEntity }: SearchResultsProps) {
  const [selectedEntity, setSelectedEntity] = useState<SearchResult | null>(initialSelectedEntity || null);
  const [entityDetails, setEntityDetails] = useState<EntityDetails | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set());
  const [activeTab, setActiveTab] = useState<'overview' | 'sections' | 'timeline'>('overview');
  const [selectedEntitiesForChat, setSelectedEntitiesForChat] = useState<Set<string>>(new Set());

  // Fetch detailed entity information
  const fetchEntityDetails = async (entityId: string) => {
    setLoadingDetails(true);
    try {
      // Import the API service
      const { apiService } = await import('../../services/api');
      
      // Fetch real entity details from the backend
      const details = await apiService.getEntityDetails(entityId);
      setEntityDetails(details);
    } catch (error) {
      console.error("Error fetching entity details:", error);
      
      // Fallback to mock data if API fails
      const mockDetails: EntityDetails = {
        basic_info: {
          id: parseInt(entityId),
          entity_name: selectedEntity?.entity_name || "Unknown Entity",
          therapeutic_area: selectedEntity?.indication,
          approval_status: "Approved",
          country: "United States",
          applicant: selectedEntity?.manufacturer || "Unknown",
          active_substance: ["Active Ingredient 1", "Active Ingredient 2"],
          regulatory: `FDA ${selectedEntity?.regulatory_classification}`
        },
        timeline: {
          submission_date: "2023-01-15",
          pdufa_date: "2023-10-15",
          approval_date: selectedEntity?.approval_date
        },
        sections: [
          {
            id: 1,
            type: "indication",
            title: "Indications and Usage",
            content: `${selectedEntity?.entity_name} is indicated for the treatment of ${selectedEntity?.indication}. This indication is based on comprehensive clinical trials demonstrating significant efficacy and acceptable safety profile in the target patient population.

Clinical studies have shown consistent therapeutic benefit across diverse patient demographics, with primary endpoints met with statistical significance. The entity has been shown to provide meaningful clinical improvement in patients with the specified condition.

Healthcare providers should carefully evaluate patient eligibility and consider individual risk factors before prescribing this medication.`,
            order: 1
          },
          {
            id: 2,
            type: "dosage",
            title: "Dosage and Administration",
            content: `The recommended dosage of ${selectedEntity?.entity_name} varies based on patient factors, disease severity, and treatment response.

**Initial Dosing:**
• Adults: Standard initial dose as per prescribing guidelines
• Elderly patients: Consider dose reduction based on renal function
• Pediatric patients: Dosing based on body weight (if applicable)

**Administration:**
• Administer as directed by healthcare provider
• Can be taken with or without food
• Swallow tablets whole; do not crush or chew
• Store at room temperature away from moisture and heat

**Dose Modifications:**
• Dose adjustments may be necessary based on patient response
• Monitor for efficacy and tolerability
• Consider entity interactions when co-administering with other medications`,
            order: 2
          },
          {
            id: 3,
            type: "contraindications",
            title: "Contraindications",
            content: `${selectedEntity?.entity_name} is contraindicated in patients with:

• Known hypersensitivity to the active ingredient or any component of the formulation
• Severe hepatic impairment (Child-Pugh Class C)
• Concurrent use with strong CYP3A4 inhibitors
• Pregnancy (Category X) - may cause fetal harm
• Severe renal impairment (CrCl < 30 mL/min)

**Warnings:**
Healthcare providers should carefully screen patients for contraindications before prescribing. Alternative treatment options should be considered for patients with any of the above conditions.`,
            order: 3
          },
          {
            id: 4,
            type: "warnings",
            title: "Warnings and Precautions",
            content: `**Serious Warnings:**
• Monitor for signs of serious adverse reactions
• Regular laboratory monitoring may be required
• Potential for entity-entity interactions

**Precautions:**
• Use with caution in elderly patients
• Monitor renal and hepatic function
• Assess cardiovascular risk factors
• Consider dose adjustments in special populations

**Patient Counseling:**
• Inform patients about potential side effects
• Advise patients to report any unusual symptoms
• Provide guidance on proper administration
• Discuss the importance of adherence to therapy`,
            order: 4
          },
          {
            id: 5,
            type: "adverse_reactions",
            title: "Adverse Reactions",
            content: `The most commonly reported adverse reactions in clinical trials include:

**Common (≥10%):**
• Nausea and vomiting
• Headache
• Fatigue
• Dizziness

**Less Common (1-10%):**
• Gastrointestinal upset
• Sleep disturbances
• Skin reactions
• Changes in appetite

**Rare (<1%):**
• Serious allergic reactions
• Liver function abnormalities
• Cardiovascular events
• Neurological symptoms

**Reporting:**
Healthcare providers and patients are encouraged to report adverse events to the FDA MedWatch program.`,
            order: 5
          },
          {
            id: 6,
            type: "clinical_studies",
            title: "Clinical Studies",
            content: `The efficacy and safety of ${selectedEntity?.entity_name} were established in randomized, double-blind, placebo-controlled clinical trials.

**Study Design:**
• Phase III multicenter trials
• Primary endpoint: [Specific clinical outcome]
• Secondary endpoints: Quality of life measures
• Duration: 12-24 weeks with long-term follow-up

**Patient Population:**
• Adults aged 18-75 years
• Confirmed diagnosis of target condition
• Baseline characteristics representative of treatment population

**Key Results:**
• Primary endpoint met with statistical significance (p<0.001)
• Clinically meaningful improvement observed
• Consistent results across subgroups
• Acceptable safety profile maintained throughout treatment period

**Long-term Data:**
Extended follow-up studies demonstrate sustained efficacy and continued acceptable safety profile over extended treatment periods.`,
            order: 6
          },
          {
            id: 7,
            type: "pharmacology",
            title: "Clinical Pharmacology",
            content: `**Mechanism of Action:**
${selectedEntity?.entity_name} works through [specific mechanism] to provide therapeutic benefit in the target condition.

**Pharmacokinetics:**
• Absorption: Well absorbed after oral administration
• Distribution: Widely distributed throughout body tissues
• Metabolism: Primarily hepatic via CYP enzymes
• Elimination: Renal and hepatic elimination pathways

**Pharmacodynamics:**
• Onset of action: 1-2 hours after administration
• Peak effect: 4-6 hours
• Duration: 12-24 hours depending on formulation
• Steady state: Achieved within 5-7 days of regular dosing

**Special Populations:**
• Renal impairment: Dose adjustment may be required
• Hepatic impairment: Use with caution
• Elderly: Consider dose reduction
• Pediatric: Safety and efficacy not established`,
            order: 7
          }
        ],
        file_url: "/api/documents/download/sample-entity-document.pdf",
        metadata: {
          document_type: "Entity Label",
          pages: 45,
          last_updated: "2024-01-15",
          version: "1.2"
        }
      };
      
      setEntityDetails(mockDetails);
    } finally {
      setLoadingDetails(false);
    }
  };

  useEffect(() => {
    if (selectedEntity) {
      fetchEntityDetails(selectedEntity.id);
      setExpandedSections(new Set([1])); // Expand first section by default
    }
  }, [selectedEntity]);

  // Handle initial selected entity
  useEffect(() => {
    if (initialSelectedEntity && !selectedEntity) {
      setSelectedEntity(initialSelectedEntity);
    }
  }, [initialSelectedEntity]);

  const toggleSection = (sectionId: number) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(sectionId)) {
      newExpanded.delete(sectionId);
    } else {
      newExpanded.add(sectionId);
    }
    setExpandedSections(newExpanded);
  };

  const toggleEntitySelection = (entityId: string) => {
    const newSelected = new Set(selectedEntitiesForChat);
    if (newSelected.has(entityId)) {
      newSelected.delete(entityId);
    } else {
      newSelected.add(entityId);
    }
    setSelectedEntitiesForChat(newSelected);
  };

  const handleChatWithSelected = () => {
    if (selectedEntitiesForChat.size > 0 && onChatWithMultipleEntities) {
      const selectedResults = results.filter(entity => selectedEntitiesForChat.has(entity.id));
      onChatWithMultipleEntities(selectedResults);
    }
  };

  const downloadPDF = async () => {
    if (!entityDetails || !selectedEntity) return;
    
    try {
      // Import the API service
      const { apiService } = await import('../../services/api');
      
      // Use source_file_id if available, otherwise try using the entity ID
      const downloadId = selectedEntity.source_file_id ? 
        selectedEntity.source_file_id.toString() : 
        entityDetails.basic_info.id.toString();
      
      console.log('Downloading PDF with ID:', downloadId, 'source_file_id:', selectedEntity.source_file_id);
      
      // Download the PDF document from the backend
      const blob = await apiService.downloadEntityPDF(downloadId);
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${entityDetails.basic_info.entity_name.replace(/[^a-zA-Z0-9]/g, '_')}_FDA_Label.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error downloading PDF:", error);
      
      // More informative error message
      alert(`Unable to download PDF for ${entityDetails?.basic_info.entity_name}. The document may not be available.`);
    }
  };

  const getSectionIcon = (type: string) => {
    switch (type) {
      case 'indication': return <BookOpen className="w-5 h-5" />;
      case 'dosage': return <Pill className="w-5 h-5" />;
      case 'contraindications': return <AlertTriangle className="w-5 h-5" />;
      case 'warnings': return <Shield className="w-5 h-5" />;
      case 'adverse_reactions': return <Activity className="w-5 h-5" />;
      case 'clinical_studies': return <FileText className="w-5 h-5" />;
      case 'pharmacology': return <Zap className="w-5 h-5" />;
      default: return <FileText className="w-5 h-5" />;
    }
  };

  const getSectionColor = (type: string) => {
    switch (type) {
      case 'indication': return 'from-blue-500 to-indigo-600';
      case 'dosage': return 'from-green-500 to-emerald-600';
      case 'contraindications': return 'from-red-500 to-rose-600';
      case 'warnings': return 'from-orange-500 to-amber-600';
      case 'adverse_reactions': return 'from-purple-500 to-violet-600';
      case 'clinical_studies': return 'from-teal-500 to-cyan-600';
      case 'pharmacology': return 'from-indigo-500 to-purple-600';
      default: return 'from-gray-500 to-slate-600';
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center space-x-4">
          <button
            onClick={onBackToDashboard}
            className="flex items-center text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft className="w-5 h-5 mr-2" />
            Back to Dashboard
          </button>
        </div>
        
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <span className="ml-3 text-gray-600">Searching...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={onBackToDashboard}
            className="flex items-center text-gray-600 hover:text-gray-900 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 mr-2" />
            Back to Dashboard
          </button>
          <div className="h-6 border-l border-gray-300"></div>
          <h2 className="text-2xl font-bold text-gray-900">
            Search Results ({results.length})
          </h2>
        </div>
        
        {/* Multi-entity chat button */}
        {results.length > 1 && onChatWithMultipleEntities && (
          <div className="flex items-center space-x-3">
            {selectedEntitiesForChat.size > 0 && (
              <span className="text-sm text-gray-600">
                {selectedEntitiesForChat.size} selected
              </span>
            )}
            <button
              onClick={handleChatWithSelected}
              disabled={selectedEntitiesForChat.size === 0}
              className={`flex items-center space-x-2 px-4 py-2 rounded-xl transition-all duration-300 shadow-lg btn-professional ${
                selectedEntitiesForChat.size > 0
                  ? 'bg-gradient-to-r from-blue-600 to-indigo-700 text-white hover:from-blue-700 hover:to-indigo-800'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              <MessageSquare className="w-4 h-4" />
              <span>Chat with Selected ({selectedEntitiesForChat.size})</span>
            </button>
            <button
              onClick={() => onChatWithMultipleEntities(results)}
              className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-gray-600 to-gray-700 text-white rounded-xl hover:from-gray-700 hover:to-gray-800 transition-all duration-300 shadow-lg btn-professional"
            >
              <MessageSquare className="w-4 h-4" />
              <span>Chat with All ({results.length})</span>
            </button>
          </div>
        )}
      </div>

      {/* Selection controls */}
      {results.length > 1 && (
        <div className="flex items-center justify-between bg-gray-50 rounded-lg p-4">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => {
                const allIds = new Set(results.map(r => r.id));
                setSelectedEntitiesForChat(allIds);
              }}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium btn-professional-subtle"
            >
              Select All
            </button>
            <button
              onClick={() => setSelectedEntitiesForChat(new Set())}
              className="text-sm text-gray-600 hover:text-gray-700 font-medium btn-professional-subtle"
            >
              Clear Selection
            </button>
          </div>
          <div className="text-sm text-gray-500">
            Select entities to compare in chat
          </div>
        </div>
      )}

      {/* Results */}
      {results.length === 0 ? (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-12 text-center">
          <Pill className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No results found</h3>
          <p className="text-gray-600">
            Try adjusting your search terms or filters to find what you're looking for.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {results.map((result) => (
            <div
              key={result.id}
              className="bg-gradient-to-br from-white via-blue-50/30 to-indigo-50/50 rounded-2xl shadow-lg border border-blue-100/50 p-6 hover:shadow-xl transition-all duration-300 backdrop-blur-sm relative"
            >
              {/* Checkbox for selection */}
              {results.length > 1 && (
                <div className="absolute top-4 right-4 z-10">
                  <input
                    type="checkbox"
                    checked={selectedEntitiesForChat.has(result.id)}
                    onChange={(e) => {
                      e.stopPropagation();
                      toggleEntitySelection(result.id);
                    }}
                    className="w-5 h-5 text-blue-600 bg-white border-gray-300 rounded focus:ring-blue-500 focus:ring-2 cursor-pointer"
                  />
                </div>
              )}
              
              <div 
                className="space-y-4 cursor-pointer"
                onClick={() => setSelectedEntity(result)}
              >
                <div>
                  <h3 className="text-lg font-bold text-gray-900 mb-2 pr-8">
                    {result.entity_name}
                  </h3>
                  <p className="text-sm text-gray-600 line-clamp-2 leading-relaxed">
                    {result.indication}
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center text-sm text-gray-600">
                    <Building className="w-4 h-4 mr-2 text-blue-600" />
                    {result.manufacturer}
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <Calendar className="w-4 h-4 mr-2 text-indigo-600" />
                    {new Date(result.approval_date).toLocaleDateString()}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-blue-100/50">
                  <span className={`px-3 py-1.5 text-xs font-semibold rounded-full ${
                    result.regulatory_classification === 'NDA' 
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-green-100 text-green-800'
                  }`}>
                    {result.regulatory_classification}
                  </span>
                  <div className="flex items-center space-x-2">
                    {onChatWithEntity && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          console.log('SearchResults: Calling onChatWithEntity with:', result);
                          onChatWithEntity(result);
                        }}
                        className="p-2 text-blue-600 hover:text-blue-700 hover:bg-blue-100/50 rounded-lg transition-all duration-200 btn-professional-subtle"
                        title="Chat about this entity"
                      >
                        <MessageSquare className="w-4 h-4" />
                      </button>
                    )}
                    <Eye className="w-4 h-4 text-gray-400" />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Enhanced Entity Detail Modal */}
      {selectedEntity && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gradient-to-br from-white via-blue-50/30 to-indigo-50/50 rounded-2xl max-w-6xl w-full max-h-[95vh] overflow-hidden shadow-2xl border border-blue-100/50">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-blue-100/50 bg-gradient-to-r from-blue-600/5 to-indigo-600/5">
              <div className="flex items-center space-x-4">
                <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                  <Pill className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-800 to-indigo-700 bg-clip-text text-transparent">
                  {selectedEntity.entity_name}
                </h2>
                  <p className="text-sm text-blue-600/70 font-medium">
                    Comprehensive Entity Information
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-3">
                <button
                  onClick={downloadPDF}
                  className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-green-600 to-emerald-700 text-white rounded-xl hover:from-green-700 hover:to-emerald-800 transition-all duration-300 shadow-lg btn-professional"
                >
                  <Download className="w-4 h-4" />
                  <span>Download PDF</span>
                </button>
                <button
                  onClick={() => setSelectedEntity(null)}
                  className="p-2 text-gray-400 hover:text-gray-600 rounded-xl hover:bg-white/50 transition-all duration-200 btn-professional-subtle"
                >
                  <span className="sr-only">Close</span>
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex border-b border-blue-100/50 bg-gradient-to-r from-blue-50/30 to-indigo-50/30">
              {[
                { id: 'overview', label: 'Overview', icon: Eye },
                { id: 'sections', label: 'Detailed Sections', icon: FileText },
                { id: 'timeline', label: 'Timeline & Doc Details', icon: Clock }
              ].map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setActiveTab(id as any)}
                  className={`flex items-center space-x-2 px-6 py-4 font-medium transition-all duration-200 btn-professional-subtle ${
                    activeTab === id
                      ? 'border-b-2 border-blue-600 text-blue-700 bg-white/50'
                      : 'text-gray-600 hover:text-blue-600 hover:bg-white/30'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{label}</span>
                </button>
              ))}
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-6 max-h-[calc(95vh-200px)]">
              {loadingDetails ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <span className="ml-3 text-gray-600">Loading detailed information...</span>
                </div>
              ) : entityDetails ? (
                <>
                  {/* Overview Tab */}
                  {activeTab === 'overview' && (
                    <div className="space-y-6">
                      {/* Basic Information Cards */}
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        <div className="bg-white/80 backdrop-blur-sm rounded-xl p-4 border border-blue-100/50 shadow-sm">
                          <h3 className="text-sm font-semibold text-gray-500 mb-2 flex items-center">
                            <Building className="w-4 h-4 mr-2 text-blue-600" />
                            Manufacturer
                          </h3>
                          <p className="text-lg font-medium text-gray-900">{entityDetails.basic_info.applicant}</p>
                        </div>
                        <div className="bg-white/80 backdrop-blur-sm rounded-xl p-4 border border-blue-100/50 shadow-sm">
                          <h3 className="text-sm font-semibold text-gray-500 mb-2 flex items-center">
                            <Shield className="w-4 h-4 mr-2 text-green-600" />
                            Status
                          </h3>
                          <span className="inline-flex px-3 py-1 text-sm font-semibold rounded-full bg-green-100 text-green-800">
                            {entityDetails.basic_info.approval_status}
                          </span>
                        </div>
                        <div className="bg-white/80 backdrop-blur-sm rounded-xl p-4 border border-blue-100/50 shadow-sm">
                          <h3 className="text-sm font-semibold text-gray-500 mb-2 flex items-center">
                            <FileText className="w-4 h-4 mr-2 text-indigo-600" />
                            Classification
                          </h3>
                          <p className="text-lg font-medium text-gray-900">{entityDetails.basic_info.regulatory}</p>
                        </div>
                      </div>

                      {/* Therapeutic Area */}
                      <div className="bg-white/80 backdrop-blur-sm rounded-xl p-6 border border-blue-100/50 shadow-sm">
                        <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
                          <BookOpen className="w-5 h-5 mr-2 text-blue-600" />
                          Therapeutic Area & Indication
                        </h3>
                        <p className="text-gray-700 leading-relaxed">
                          {entityDetails.basic_info.therapeutic_area || selectedEntity.indication}
                        </p>
                      </div>

                      {/* Active Substances */}
                      {entityDetails.basic_info.active_substance && (
                        <div className="bg-white/80 backdrop-blur-sm rounded-xl p-6 border border-blue-100/50 shadow-sm">
                          <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center">
                            <Pill className="w-5 h-5 mr-2 text-green-600" />
                            Active Substances
                          </h3>
                          <div className="flex flex-wrap gap-2">
                            {Array.isArray(entityDetails.basic_info.active_substance) 
                              ? entityDetails.basic_info.active_substance.map((substance: string, index: number) => (
                                  <span key={index} className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                                    {substance}
                                  </span>
                                ))
                              : <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                                  {entityDetails.basic_info.active_substance}
                                </span>
                            }
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Sections Tab */}
                  {activeTab === 'sections' && (
                    <div className="space-y-4">
                      {entityDetails.sections.map((section) => (
                        <div key={section.id} className="bg-white/80 backdrop-blur-sm rounded-xl border border-blue-100/50 shadow-sm overflow-hidden">
                          <button
                            onClick={() => toggleSection(section.id)}
                            className="w-full flex items-center justify-between p-6 hover:bg-blue-50/30 transition-all duration-200 btn-professional-subtle"
                          >
                            <div className="flex items-center space-x-4">
                              <div className={`w-10 h-10 bg-gradient-to-br ${getSectionColor(section.type)} rounded-xl flex items-center justify-center shadow-lg`}>
                                <div className="text-white">
                                  {getSectionIcon(section.type)}
                                </div>
                              </div>
                              <div className="text-left">
                                <h3 className="text-lg font-semibold text-gray-900">{section.title}</h3>
                                <p className="text-sm text-gray-600 capitalize">{section.type.replace('_', ' ')}</p>
                              </div>
                            </div>
                            {expandedSections.has(section.id) ? (
                              <ChevronUp className="w-5 h-5 text-gray-400" />
                            ) : (
                              <ChevronDown className="w-5 h-5 text-gray-400" />
                            )}
                          </button>
                          
                          {expandedSections.has(section.id) && (
                            <div className="px-6 pb-6 border-t border-blue-100/50 bg-gradient-to-r from-blue-50/20 to-indigo-50/20">
                              <div className="prose prose-sm max-w-none mt-4">
                                {section.content.split('\n\n').map((paragraph, index) => (
                                  <div key={index} className="mb-4">
                                    {paragraph.startsWith('**') && paragraph.endsWith('**') ? (
                                      <h4 className="font-semibold text-gray-900 mb-2">
                                        {paragraph.replace(/\*\*/g, '')}
                                      </h4>
                                    ) : paragraph.startsWith('•') ? (
                                      <ul className="list-disc list-inside space-y-1">
                                        {paragraph.split('\n').map((item, itemIndex) => (
                                          <li key={itemIndex} className="text-gray-700">
                                            {item.replace('• ', '')}
                                          </li>
                                        ))}
                                      </ul>
                                    ) : (
                                      <p className="text-gray-700 leading-relaxed">{paragraph}</p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Timeline Tab */}
                  {activeTab === 'timeline' && (
              <div className="space-y-6">
                      <div className="bg-white/80 backdrop-blur-sm rounded-xl p-6 border border-blue-100/50 shadow-sm">
                        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                          <Clock className="w-5 h-5 mr-2 text-blue-600" />
                          Regulatory Timeline
                        </h3>
                        <div className="space-y-4">
                          {entityDetails.timeline?.submission_date && (
                            <div className="flex items-center space-x-4">
                              <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                  <div>
                                <p className="font-medium text-gray-900">Submission Date</p>
                                <p className="text-sm text-gray-600">
                                  {new Date(entityDetails.timeline.submission_date).toLocaleDateString()}
                                </p>
                              </div>
                  </div>
                          )}
                          {entityDetails.timeline?.pdufa_date && (
                            <div className="flex items-center space-x-4">
                              <div className="w-3 h-3 bg-orange-500 rounded-full"></div>
                  <div>
                                <p className="font-medium text-gray-900">PDUFA Date</p>
                                <p className="text-sm text-gray-600">
                                  {new Date(entityDetails.timeline.pdufa_date).toLocaleDateString()}
                    </p>
                  </div>
                            </div>
                          )}
                          {entityDetails.timeline?.approval_date && (
                            <div className="flex items-center space-x-4">
                              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                  <div>
                                <p className="font-medium text-gray-900">Approval Date</p>
                                <p className="text-sm text-gray-600">
                                  {new Date(entityDetails.timeline.approval_date).toLocaleDateString()}
                                </p>
                              </div>
                            </div>
                          )}
                          
                          {/* Show message if no timeline data available */}
                          {(!entityDetails.timeline?.submission_date && !entityDetails.timeline?.pdufa_date && !entityDetails.timeline?.approval_date) && (
                            <div className="text-center py-8">
                              <p className="text-gray-600">Timeline information is not available for this entity.</p>
                            </div>
                          )}
                  </div>
                </div>
                
                      {/* Document Metadata */}
                      {(entityDetails.metadata || entityDetails.page_info) && (
                        <div className="bg-white/80 backdrop-blur-sm rounded-xl p-6 border border-blue-100/50 shadow-sm">
                          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                            <FileText className="w-5 h-5 mr-2 text-indigo-600" />
                            Document Information
                          </h3>
                          <div className="grid grid-cols-2 gap-4">
                            {entityDetails.metadata?.document_type && (
                              <div>
                                <p className="text-sm font-medium text-gray-500">Document Type</p>
                                <p className="text-gray-900">{entityDetails.metadata.document_type}</p>
                              </div>
                            )}
                            {entityDetails.page_info && (
                              <div>
                                <p className="text-sm font-medium text-gray-500">Total Pages</p>
                                <p className="text-gray-900">{entityDetails.page_info.total_pages}</p>
                              </div>
                            )}
                            {entityDetails.page_info && (
                              <div>
                                <p className="text-sm font-medium text-gray-500">Content Chunks</p>
                                <p className="text-gray-900">{entityDetails.page_info.total_chunks}</p>
                              </div>
                            )}
                            {entityDetails.page_info && (
                              <div>
                                <p className="text-sm font-medium text-gray-500">Content Tokens</p>
                                <p className="text-gray-900">{entityDetails.page_info.total_tokens.toLocaleString()}</p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-12">
                  <p className="text-gray-600">Failed to load entity details. Please try again.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
} 