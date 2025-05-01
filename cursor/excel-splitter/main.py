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

def process_excel(config):
    """Process Excel file according to configuration."""
    input_path = config['input']['path']
    output_path = config['output']['path']
    source_sheet = config['input']['sheet']['source']['name']
    result_sheet = config['output']['sheet']['result']['name']

    # Check if input file exists
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' does not exist")
        sys.exit(1)

    try:
        # Load the source workbook
        wb = load_workbook(input_path)
        
        # Check if source sheet exists
        if source_sheet not in wb.sheetnames:
            print(f"Error: Sheet '{source_sheet}' does not exist")
            sys.exit(1)

        # Get the source sheet
        source = wb[source_sheet]
        
        # Create a new workbook for output
        output_wb = load_workbook(input_path)
        
        # If result sheet exists, remove it
        if result_sheet in output_wb.sheetnames:
            output_wb.remove(output_wb[result_sheet])
        
        # Create new sheet with the same name as source
        result = output_wb.create_sheet(result_sheet)
        
        # Copy all cells including values, formulas, and formatting
        for row in source.rows:
            for cell in row:
                # Create new cell in result sheet
                new_cell = result.cell(row=cell.row, column=cell.column)
                
                # Copy value
                new_cell.value = cell.value
                
                # Copy formatting
                copy_cell_style(cell, new_cell)

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