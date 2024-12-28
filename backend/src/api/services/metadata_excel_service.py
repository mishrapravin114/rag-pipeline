"""
Service layer for Excel import/export of metadata configurations.
Handles template generation, validation, and processing.
"""
import io
import pandas as pd
from typing import List, Dict, Any, Optional, BinaryIO, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
import logging

from database.database import MetadataConfiguration, MetadataGroup

logger = logging.getLogger(__name__)

class MetadataExcelService:
    """Service for handling Excel import/export operations"""
    
    # Column definitions for Excel template
    EXCEL_COLUMNS = {
        'name': 'Configuration Name',
        'description': 'Description',
        'data_type': 'Data Type',
        'extraction_prompt': 'Extraction Prompt',
        'validation_rules': 'Validation Rules (JSON)',
        'is_active': 'Active (TRUE/FALSE)',
        'display_order': 'Display Order',
        'groups': 'Group Names (comma-separated)'
    }
    
    # Valid data types
    VALID_DATA_TYPES = ['text', 'number', 'date', 'boolean']
    
    @staticmethod
    def generate_template() -> bytes:
        """
        Generate an Excel template for importing metadata configurations.
        Returns the Excel file as bytes.
        """
        # Create a DataFrame with column headers
        template_data = {
            MetadataExcelService.EXCEL_COLUMNS['name']: ['Example: Drug Name', 'Example: Indication'],
            MetadataExcelService.EXCEL_COLUMNS['description']: [
                'The brand name of the drug',
                'Primary therapeutic indication'
            ],
            MetadataExcelService.EXCEL_COLUMNS['data_type']: ['text', 'text'],
            MetadataExcelService.EXCEL_COLUMNS['extraction_prompt']: [
                'Extract the brand name of this drug',
                'Extract the primary indication for this drug'
            ],
            MetadataExcelService.EXCEL_COLUMNS['validation_rules']: ['{}', '{"required": true}'],
            MetadataExcelService.EXCEL_COLUMNS['is_active']: ['TRUE', 'TRUE'],
            MetadataExcelService.EXCEL_COLUMNS['groups']: ['General', 'General,Clinical']
        }
        
        df = pd.DataFrame(template_data)
        
        # Create Excel writer with formatting
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Metadata Configurations', index=False)
            
            # Get the worksheet
            worksheet = writer.sheets['Metadata Configurations']
            
            # Add instructions sheet
            instructions_df = pd.DataFrame({
                'Instructions': [
                    'How to use this template:',
                    '',
                    '1. Configuration Name: Unique name for the metadata field',
                    '2. Description: Detailed description of what this field captures',
                    '3. Data Type: Must be one of: text, number, date, boolean',
                    '4. Extraction Prompt: The prompt used to extract this information',
                    '5. Validation Rules: JSON object with validation rules (optional)',
                    '6. Active: TRUE or FALSE to enable/disable the configuration',
                    '7. Group Names: Comma-separated list of group names',
                    '',
                    'Notes:',
                    '- Each configuration must belong to at least one group',
                    '- If a group doesn\'t exist, it will be created',
                    '- Duplicate configuration names will be skipped',
                    '- Leave validation rules as {} if not needed'
                ]
            })
            instructions_df.to_excel(writer, sheet_name='Instructions', index=False)
            
            # Format the main worksheet
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        return output.getvalue()
    
    @staticmethod
    def validate_import_data(df: pd.DataFrame) -> Tuple[bool, List[Dict[str, Any]], List[str]]:
        """
        Validate imported Excel data.
        Returns: (is_valid, processed_rows, errors)
        """
        errors = []
        processed_rows = []
        
        # Check required columns
        required_columns = [
            MetadataExcelService.EXCEL_COLUMNS['name'],
            MetadataExcelService.EXCEL_COLUMNS['data_type'],
            MetadataExcelService.EXCEL_COLUMNS['extraction_prompt'],
            MetadataExcelService.EXCEL_COLUMNS['groups']
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            errors.append(f"Missing required columns: {', '.join(missing_columns)}")
            return False, [], errors
        
        # Process each row
        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel row number (1-indexed + header)
            row_errors = []
            
            # Validate configuration name
            name = str(row.get(MetadataExcelService.EXCEL_COLUMNS['name'], '')).strip()
            if not name:
                row_errors.append(f"Row {row_num}: Configuration name is required")
            
            # Validate data type
            data_type = str(row.get(MetadataExcelService.EXCEL_COLUMNS['data_type'], '')).strip().lower()
            if data_type not in MetadataExcelService.VALID_DATA_TYPES:
                row_errors.append(f"Row {row_num}: Invalid data type '{data_type}'. Must be one of: {', '.join(MetadataExcelService.VALID_DATA_TYPES)}")
            
            # Validate extraction prompt
            prompt = str(row.get(MetadataExcelService.EXCEL_COLUMNS['extraction_prompt'], '')).strip()
            if not prompt:
                row_errors.append(f"Row {row_num}: Extraction prompt is required")
            
            # Validate groups
            groups_str = str(row.get(MetadataExcelService.EXCEL_COLUMNS['groups'], '')).strip()
            if not groups_str:
                row_errors.append(f"Row {row_num}: At least one group is required")
            
            groups = [g.strip() for g in groups_str.split(',') if g.strip()]
            if not groups:
                row_errors.append(f"Row {row_num}: At least one valid group name is required")
            
            # Validate boolean fields
            is_active_str = str(row.get(MetadataExcelService.EXCEL_COLUMNS['is_active'], 'TRUE')).strip().upper()
            if is_active_str not in ['TRUE', 'FALSE']:
                row_errors.append(f"Row {row_num}: Active field must be TRUE or FALSE")
            
            # Validate display order
            try:
                display_order = int(row.get(MetadataExcelService.EXCEL_COLUMNS['display_order'], 0))
            except:
                display_order = 0
                row_errors.append(f"Row {row_num}: Display order must be a number")
            
            # Validate JSON fields
            validation_rules = row.get(MetadataExcelService.EXCEL_COLUMNS['validation_rules'], '{}')
            if pd.isna(validation_rules) or validation_rules == '':
                validation_rules = '{}'
            
            try:
                import json
                json.loads(str(validation_rules))
            except:
                row_errors.append(f"Row {row_num}: Validation rules must be valid JSON")
            
            if row_errors:
                errors.extend(row_errors)
            else:
                # Process the row
                processed_row = {
                    'name': name,
                    'description': str(row.get(MetadataExcelService.EXCEL_COLUMNS['description'], '')).strip(),
                    'data_type': data_type,
                    'extraction_prompt': prompt,
                    'validation_rules': validation_rules,
                    'is_active': is_active_str == 'TRUE',
                    'display_order': display_order,
                    'groups': groups,
                    'row_number': row_num
                }
                processed_rows.append(processed_row)
        
        is_valid = len(errors) == 0
        return is_valid, processed_rows, errors
    
    @staticmethod
    def import_configurations(
        db: Session,
        file_content: bytes,
        user_id: int,
        skip_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Import metadata configurations from Excel file.
        Returns summary of import results.
        """
        result = {
            'success': False,
            'imported': 0,
            'skipped': 0,
            'errors': [],
            'created_groups': [],
            'details': []
        }
        
        try:
            # Read Excel file
            df = pd.read_excel(io.BytesIO(file_content), sheet_name='Metadata Configurations')
            
            # Validate data
            is_valid, processed_rows, errors = MetadataExcelService.validate_import_data(df)
            
            if not is_valid:
                result['errors'] = errors
                return result
            
            # Process each validated row
            for row_data in processed_rows:
                try:
                    # Check for duplicate
                    existing = db.query(MetadataConfiguration).filter(
                        MetadataConfiguration.name == row_data['name']
                    ).first()
                    
                    if existing and skip_duplicates:
                        result['skipped'] += 1
                        result['details'].append({
                            'row': row_data['row_number'],
                            'name': row_data['name'],
                            'status': 'skipped',
                            'reason': 'Configuration already exists'
                        })
                        continue
                    
                    # Get or create groups
                    group_objects = []
                    for group_name in row_data['groups']:
                        group = db.query(MetadataGroup).filter(
                            MetadataGroup.name == group_name
                        ).first()
                        
                        if not group:
                            # Create new group
                            group = MetadataGroup(
                                name=group_name,
                                description=f"Created from import on {datetime.now().strftime('%Y-%m-%d')}",
                                color='#6B7280',  # Default gray color
                                created_by=user_id
                            )
                            db.add(group)
                            db.flush()
                            result['created_groups'].append(group_name)
                        
                        group_objects.append(group)
                    
                    # Create or update configuration
                    if existing and not skip_duplicates:
                        # Update existing
                        existing.description = row_data['description']
                        existing.data_type = row_data['data_type']
                        existing.extraction_prompt = row_data['extraction_prompt']
                        existing.extraction_prompt_version += 1
                        existing.validation_rules = row_data['validation_rules']
                        existing.is_active = row_data['is_active']
                        existing.display_order = row_data['display_order']
                        existing.updated_at = datetime.utcnow()
                        
                        # Update groups
                        existing.groups = group_objects
                        
                        config = existing
                        action = 'updated'
                    else:
                        # Create new
                        config = MetadataConfiguration(
                            name=row_data['name'],
                            description=row_data['description'],
                            data_type=row_data['data_type'],
                            extraction_prompt=row_data['extraction_prompt'],
                            extraction_prompt_version=1,
                            validation_rules=row_data['validation_rules'],
                            is_active=row_data['is_active'],
                            display_order=row_data['display_order'],
                            created_by=user_id
                        )
                        config.groups = group_objects
                        db.add(config)
                        action = 'imported'
                    
                    db.flush()
                    result['imported'] += 1
                    result['details'].append({
                        'row': row_data['row_number'],
                        'name': row_data['name'],
                        'status': 'success',
                        'action': action
                    })
                    
                except Exception as e:
                    result['errors'].append(f"Row {row_data['row_number']}: {str(e)}")
                    result['details'].append({
                        'row': row_data['row_number'],
                        'name': row_data['name'],
                        'status': 'error',
                        'reason': str(e)
                    })
            
            # Commit all changes
            db.commit()
            result['success'] = True
            
        except Exception as e:
            db.rollback()
            result['errors'].append(f"Import failed: {str(e)}")
            logger.error(f"Excel import error: {e}")
        
        return result
    
    @staticmethod
    def export_configurations(
        db: Session,
        group_ids: Optional[List[int]] = None,
        active_only: bool = True
    ) -> bytes:
        """
        Export metadata configurations to Excel.
        Can filter by groups and active status.
        """
        # Build query
        query = db.query(MetadataConfiguration)
        
        if group_ids:
            query = query.join(MetadataConfiguration.groups).filter(
                MetadataGroup.id.in_(group_ids)
            )
        
        if active_only:
            query = query.filter(MetadataConfiguration.is_active == True)
        
        # Order by name (display_order is now per-group)
        configs = query.order_by(MetadataConfiguration.metadata_name).all()
        
        # Build export data
        export_data = []
        for config in configs:
            # Get group names
            group_names = ','.join([g.name for g in config.groups])
            
            export_data.append({
                MetadataExcelService.EXCEL_COLUMNS['name']: config.name,
                MetadataExcelService.EXCEL_COLUMNS['description']: config.description or '',
                MetadataExcelService.EXCEL_COLUMNS['data_type']: config.data_type,
                MetadataExcelService.EXCEL_COLUMNS['extraction_prompt']: config.extraction_prompt,
                MetadataExcelService.EXCEL_COLUMNS['validation_rules']: config.validation_rules or '{}',
                MetadataExcelService.EXCEL_COLUMNS['is_active']: 'TRUE' if config.is_active else 'FALSE',
                MetadataExcelService.EXCEL_COLUMNS['display_order']: config.display_order,
                MetadataExcelService.EXCEL_COLUMNS['groups']: group_names
            })
        
        # Create DataFrame
        df = pd.DataFrame(export_data)
        
        # Export to Excel with formatting
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Metadata Configurations', index=False)
            
            # Format columns
            worksheet = writer.sheets['Metadata Configurations']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Add metadata sheet with export info
            metadata = pd.DataFrame({
                'Export Information': [
                    f'Export Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                    f'Total Configurations: {len(configs)}',
                    f'Active Only: {"Yes" if active_only else "No"}',
                    f'Filtered by Groups: {"Yes" if group_ids else "No"}'
                ]
            })
            metadata.to_excel(writer, sheet_name='Export Info', index=False)
        
        output.seek(0)
        return output.getvalue()