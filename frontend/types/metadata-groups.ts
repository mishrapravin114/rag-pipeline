// Minor update
export interface MetadataGroup {
  id: number;
  name: string;
  description: string;
  color?: string;
  tags?: string[];
  is_default?: boolean;
  metadata_count: number;
  created_at: string;
  updated_at: string;
  created_by?: number;
  items?: MetadataGroupItem[];
}

export interface MetadataGroupItem {
  id: number;
  metadata_config_id: number;
  metadata_name: string;
  extraction_prompt: string;
  display_order: number;
}

export interface MetadataConfiguration {
  id: number;
  metadata_name: string;
  description: string;
  data_type: DataType;
  extraction_prompt: string;
  extraction_prompt_version: number;
  is_active: boolean;
  display_order: number;
  created_at: string;
  updated_at: string;
  created_by?: number;
  validation_rules?: ValidationRules;
  groups?: number[];
  is_in_group?: boolean;
}

export type DataType = 'text' | 'number' | 'date' | 'boolean';

export interface ValidationRules {
  required?: boolean;
  min?: number;
  max?: number;
  pattern?: string;
  options?: string[];
}

export interface ExtractionHistory {
  id: number;
  document_id: number;
  config_id: number;
  prompt_version: number;
  extracted_value: any;
  extraction_date: string;
  success: boolean;
}

export interface BulkOperationResult {
  success: number;
  failed: number;
  errors: Array<{
    id: number;
    error: string;
  }>;
}

export interface ImportPreview {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicates: number;
  configurations: Array<{
    row_number: number;
    metadata_name: string;
    description: string;
    data_type: string;
    extraction_prompt: string;
    errors?: string[];
    is_duplicate?: boolean;
  }>;
}