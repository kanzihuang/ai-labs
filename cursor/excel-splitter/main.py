#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import yaml
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from copy import copy

def load_config(config_path):
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config file: {e}")
        sys.exit(1)

def copy_cell_style(source_cell, target_cell):
    """Copy cell style from source to target cell."""
    if source_cell.has_style:
        target_cell.font = copy(source_cell.font)
        target_cell.border = copy(source_cell.border)
        target_cell.fill = copy(source_cell.fill)
        target_cell.number_format = source_cell.number_format
        target_cell.alignment = copy(source_cell.alignment)
        target_cell.protection = copy(source_cell.protection)

def get_column_index(headers, column_name):
    """Get column index (1-based) for a given column name."""
    try:
        return headers.index(column_name) + 1
    except ValueError:
        return None

def split_row(source_row, reference_rows, source_headers, reference_headers, config):
    """Split a row based on reference data."""
    employee_id_col = get_column_index(source_headers, config['input']['sheet']['source']['columns']['employee_id'])
    employee_id = source_row[employee_id_col - 1].value

    # Find matching rows in reference sheet
    matching_ref_rows = []
    for ref_row in reference_rows:
        ref_employee_id = ref_row[get_column_index(reference_headers, config['input']['sheet']['reference']['columns']['employee_id']) - 1].value
        if ref_employee_id == employee_id:
            matching_ref_rows.append(ref_row)

    if not matching_ref_rows:
        # No matching reference rows, copy source row as is
        return [source_row]

    # 计算reference表中匹配行的总工时
    total_ref_hours = 0
    for ref_row in matching_ref_rows:
        ref_hours_col = get_column_index(reference_headers, config['input']['sheet']['reference']['columns']['project_hours'])
        ref_hours = float(ref_row[ref_hours_col - 1].value)
        total_ref_hours += ref_hours

    if total_ref_hours == 0:
        # 如果总工时为0，直接复制原行
        return [source_row]

    # Split the row
    result_rows = []
    for ref_row in matching_ref_rows:
        ref_hours_col = get_column_index(reference_headers, config['input']['sheet']['reference']['columns']['project_hours'])
        ref_hours = float(ref_row[ref_hours_col - 1].value)
        ratio = ref_hours / total_ref_hours  # 根据reference表中的总工时计算比例

        # Create new row with same style as source
        new_row = []
        for cell in source_row:
            new_cell = copy(cell)
            if cell.value is not None and cell.column in [
                get_column_index(source_headers, col_name)
                for col_name in config['input']['splitting_columns']
            ]:
                # Split numeric values
                try:
                    new_cell.value = float(cell.value) * ratio
                except (ValueError, TypeError):
                    new_cell.value = cell.value
            new_row.append(new_cell)

        # 只更新project_id, project_category, project_hours这三列
        project_id_col = get_column_index(source_headers, config['input']['sheet']['source']['columns']['project_id'])
        project_category_col = get_column_index(source_headers, config['input']['sheet']['source']['columns']['project_category'])
        project_hours_col = get_column_index(source_headers, config['input']['sheet']['source']['columns']['project_hours'])
        
        ref_project_id_col = get_column_index(reference_headers, config['input']['sheet']['reference']['columns']['project_id'])
        ref_project_category_col = get_column_index(reference_headers, config['input']['sheet']['reference']['columns']['project_category'])
        ref_project_hours_col = get_column_index(reference_headers, config['input']['sheet']['reference']['columns']['project_hours'])
        
        if project_id_col and ref_project_id_col:
            new_row[project_id_col - 1].value = ref_row[ref_project_id_col - 1].value
            
        if project_category_col and ref_project_category_col:
            new_row[project_category_col - 1].value = ref_row[ref_project_category_col - 1].value
            
        if project_hours_col and ref_project_hours_col:
            new_row[project_hours_col - 1].value = ref_row[ref_project_hours_col - 1].value

        result_rows.append(new_row)

    return result_rows

def validate_sheets(config, wb):
    """Validate that required sheets and columns exist."""
    source_sheet = config['input']['sheet']['source']['name']
    reference_sheet = config['input']['sheet']['reference']['name']
    
    # Check if sheets exist
    if source_sheet not in wb.sheetnames:
        print(f"Error: Source sheet '{source_sheet}' does not exist")
        sys.exit(1)
    if reference_sheet not in wb.sheetnames:
        print(f"Error: Reference sheet '{reference_sheet}' does not exist")
        sys.exit(1)

    source = wb[source_sheet]
    reference = wb[reference_sheet]

    # Get header rows
    source_headers = [cell.value for cell in source[1]]
    reference_headers = [cell.value for cell in reference[1]]

    # Validate required columns in source sheet
    required_source_columns = {
        'employee_id': config['input']['sheet']['source']['columns']['employee_id']
    }
    for col_id, col_name in required_source_columns.items():
        if col_name not in source_headers:
            print(f"Error: Required column '{col_name}' not found in source sheet")
            sys.exit(1)

    # Validate splitting columns in source sheet
    for col_name in config['input']['splitting_columns']:
        if col_name not in source_headers:
            print(f"Error: Splitting column '{col_name}' not found in source sheet")
            sys.exit(1)

    # Validate required columns in reference sheet
    required_ref_columns = {
        'employee_id': config['input']['sheet']['reference']['columns']['employee_id'],
        'project_id': config['input']['sheet']['reference']['columns']['project_id'],
        'project_category': config['input']['sheet']['reference']['columns']['project_category'],
        'project_hours': config['input']['sheet']['reference']['columns']['project_hours']
    }
    for col_id, col_name in required_ref_columns.items():
        if col_name not in reference_headers:
            print(f"Error: Required column '{col_name}' not found in reference sheet")
            sys.exit(1)

    return source, reference, source_headers, reference_headers

def process_excel(config):
    """Process Excel file according to configuration."""
    input_path = config['input']['path']
    output_path = config['output']['path']
    result_sheet = config['output']['sheet']['result']['name']

    # Check if input file exists
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' does not exist")
        sys.exit(1)

    try:
        # Load the workbook
        wb = load_workbook(input_path)
        
        # Validate sheets and columns
        source, reference, source_headers, reference_headers = validate_sheets(config, wb)
        
        # Create a new workbook for output
        output_wb = load_workbook(input_path)
        
        # If result sheet exists, remove it
        if result_sheet in output_wb.sheetnames:
            output_wb.remove(output_wb[result_sheet])
        
        # Create new sheet
        result = output_wb.create_sheet(result_sheet)
        
        # Copy headers
        for cell in source[1]:
            new_cell = result.cell(row=1, column=cell.column)
            new_cell.value = cell.value
            copy_cell_style(cell, new_cell)

        # Process data rows
        current_row = 2
        reference_rows = list(reference.iter_rows(min_row=2))  # Convert iterator to list
        for row in source.iter_rows(min_row=2):
            split_result_rows = split_row(row, reference_rows, source_headers, reference_headers, config)
            for result_row in split_result_rows:
                for cell in result_row:
                    new_cell = result.cell(row=current_row, column=cell.column)
                    new_cell.value = cell.value
                    copy_cell_style(cell, new_cell)
                current_row += 1

        # Copy column dimensions
        for col in source.column_dimensions:
            result.column_dimensions[col].width = source.column_dimensions[col].width

        # Copy row dimensions
        for row in source.row_dimensions:
            result.row_dimensions[row].height = source.row_dimensions[row].height

        # Save the output file
        output_wb.save(output_path)
        
    except InvalidFileException:
        print(f"Error: Invalid Excel file '{input_path}'")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing Excel file: {e}")
        sys.exit(1)

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Process Excel file according to configuration')
    parser.add_argument('--config', default='config.yaml', help='Path to configuration file')
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    
    # Process Excel file
    process_excel(config)

if __name__ == '__main__':
    main() 