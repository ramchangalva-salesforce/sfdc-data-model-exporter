"""File and CSV processing service."""
import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from config import get_settings
from models import MetadataRow, LucidRow

logger = logging.getLogger(__name__)
settings = get_settings()


class FileService:
    """Service for file operations and CSV processing."""
    
    def __init__(self):
        """Initialize the file service."""
        self.input_dir = settings.input_dir
        self.output_dir = settings.output_dir
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Ensure input and output directories exist."""
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
    
    def save_metadata_csv(self, metadata_rows: List[MetadataRow]) -> str:
        """
        Save metadata to CSV file.
        
        Args:
            metadata_rows: List of metadata rows to save
            
        Returns:
            Path to the saved CSV file
        """
        df = pd.DataFrame(metadata_rows)
        file_path = os.path.join(self.input_dir, 'salesforce_metadata.csv')
        df.to_csv(file_path, index=False)
        logger.info(f"Metadata saved to {file_path}")
        return file_path
    
    @staticmethod
    def _format_date() -> str:
        """Format current date for filename."""
        return datetime.now().replace(microsecond=0).strftime('%Y_%m_%d')
    
    @staticmethod
    def map_data_type(data_type: str) -> Tuple[str, str, str, str]:
        """
        Map Salesforce data type to database type.
        
        Args:
            data_type: Salesforce field type
            
        Returns:
            Tuple of (database_type, constraint_type, referenced_table_name, column_length)
        """
        type_mapping = {
            'id': ("INT", "Primary Key", "", "11"),
            'reference': ("INT", "Foreign Key", "reference", "11"),
            'int': ("INT", "", "", "11"),
            'boolean': ("INT", "", "", "1"),
            'datetime': ("DATETIME", "", "", ""),
            'date': ("DATE", "", "", ""),
            'percent': ("FLOAT", "", "", "18"),
            'string': ("TEXT", "", "", ""),
            'textarea': ("TEXT", "", "", ""),
            'json': ("TEXT", "", "", ""),
        }
        
        return type_mapping.get(data_type, ("VARCHAR", "", "", "255"))
    
    def generate_lucid_csv(self, metadata_file_path: str, app_name: Optional[str] = None) -> str:
        """
        Generate Lucidchart-compatible CSV from metadata CSV.
        
        Args:
            metadata_file_path: Path to the metadata CSV file
            app_name: Optional app name to include in filename
            
        Returns:
            Path to the generated Lucidchart CSV file
        """
        logger.info(f"Generating Lucidchart CSV from {metadata_file_path}")
        
        # Read metadata CSV
        with open(metadata_file_path, 'r', newline='', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            csv_data = list(csv_reader)
        
        # Prepare output data with headers
        output_data: List[List[str]] = [[
            "dbms", "TABLE_SCHEMA", "TABLE_NAME", "COLUMN_NAME", 
            "ORDINAL_POSITION", "DATA_TYPE", "CHARACTER_MAXIMUM_LENGTH", 
            "CONSTRAINT_TYPE", "REFERENCED_TABLE_SCHEMA", "REFERENCED_TABLE_NAME", 
            "REFERENCED_COLUMN_NAME", "COMMENT"
        ]]
        
        position_index = 0
        last_table = ''
        
        # Process each row (skip header)
        for row in csv_data[1:]:
            if len(row) < 8:
                continue
                
            table_object, table_field, table_type, _, _, _, table_reference_to, _ = row
            
            # Reset position index for new table
            if last_table != table_object:
                last_table = table_object
                position_index = 0
            position_index += 1
            
            # Map data type
            mapped_data_type, constraint_type, referenced_table_name, column_length = \
                self.map_data_type(table_type)
            
            # Determine referenced column
            referenced_column = "Id" if referenced_table_name == 'reference' else ''
            
            # Parse reference table
            reference_tables = table_reference_to.split(',')
            table_reference = reference_tables[-1] if len(reference_tables) > 1 else reference_tables[0]
            
            # Append row
            output_data.append([
                "mysql",
                "dbo",
                table_object,
                table_field,
                str(position_index),
                mapped_data_type,
                column_length,
                constraint_type,
                "dbo",
                table_reference,
                referenced_column,
                ""
            ])
        
        # Write output file with app name in filename
        date_str = self._format_date()
        if app_name:
            # Sanitize app name for filename
            safe_app_name = "".join(c for c in app_name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
            output_filename = f"{date_str}_{safe_app_name}_salesforce_metadata_lucid.csv"
        else:
            output_filename = f"{date_str}_salesforce_metadata_lucid.csv"
        output_file_path = os.path.join(self.output_dir, output_filename)
        
        with open(output_file_path, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(output_data)
        
        logger.info(f"Lucidchart CSV generated at {output_file_path}")
        return output_file_path
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file exists, False otherwise
        """
        return os.path.exists(file_path) and os.path.isfile(file_path)

