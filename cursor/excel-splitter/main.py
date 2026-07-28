#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import traceback
import yaml
from openpyxl import load_workbook
from openpyxl.cell import Cell
from openpyxl.utils.exceptions import InvalidFileException
from copy import copy, deepcopy

def load_config(config_path):
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        fatal(f"Error loading config file: {e}")

def copy_cell_style(source_cell, target_cell):
    """Copy cell style from source to target cell."""
    if source_cell.has_style:
        try:
            target_cell.font = copy(source_cell.font)
            target_cell.border = copy(source_cell.border)
            target_cell.fill = copy(source_cell.fill)
            target_cell.number_format = source_cell.number_format
            target_cell.alignment = copy(source_cell.alignment)
            target_cell.protection = copy(source_cell.protection)
        except (IndexError, AttributeError):
            pass

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
        return [list(source_row)]

    # 计算reference表中匹配行的总工时
    total_ref_hours = 0
    for ref_row in matching_ref_rows:
        ref_hours_col = get_column_index(reference_headers, config['input']['sheet']['reference']['columns']['project_hours'])
        ref_hours = float(ref_row[ref_hours_col - 1].value)
        total_ref_hours += ref_hours

    if total_ref_hours == 0:
        # 如果总工时为0，直接复制原行
        return [list(source_row)]

    # Split the row
    remain_row = deepcopy(source_row)
    result_rows = []
    for i, ref_row in enumerate(matching_ref_rows):
        ref_hours_col = get_column_index(reference_headers, config['input']['sheet']['reference']['columns']['project_hours'])
        ref_hours = float(ref_row[ref_hours_col - 1].value)
        ratio = ref_hours / total_ref_hours  # 根据reference表中的总工时计算比例

        # Create new row with same style as source
        new_row = []
        for j, cell in enumerate(source_row):
            new_cell = copy(cell)
            if cell.value is not None and cell.column in [
                get_column_index(source_headers, col_name)
                for col_name in config['input']['splitting_columns']
            ]:
                # Split numeric values
                try:
                    if i < len(matching_ref_rows) - 1 :
                        new_cell.value = round(float(cell.value) * ratio, 2)
                        remain_row[j].value -= new_cell.value
                    else:
                        new_cell.value = remain_row[j].value
                except (ValueError, TypeError):
                    fatal(f"Error: 无法拆分'{source_headers[j]}:{source_row[j].value}'")
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

def merge_rows_by_account(split_rows, source_headers, payment_mapping, config):
    """Merge split result rows by (employee_id, project_account)."""
    if not split_rows:
        return []

    employee_id_col = get_column_index(source_headers, config['input']['sheet']['source']['columns']['employee_id'])
    project_id_col = get_column_index(source_headers, config['input']['sheet']['source']['columns']['project_id'])
    project_category_col = get_column_index(source_headers,
                                            config['input']['sheet']['source']['columns']['project_category'])
    project_hours_col = get_column_index(source_headers, config['input']['sheet']['source']['columns']['project_hours'])
    project_account_col = get_column_index(source_headers,
                                            config['input']['sheet']['source']['columns']['project_account'])

    splitting_col_indices = [
        get_column_index(source_headers, col_name)
        for col_name in config['input']['splitting_columns']
    ]

    # Ensure all split rows have enough cells for project_account column
    # (source sheet may not have the project_account column)
    max_cols = len(source_headers)
    if project_account_col:
        for row in split_rows:
            while len(row) < max_cols:
                dummy = Cell(None, column=len(row) + 1)
                dummy.value = None
                dummy._style = copy(row[0]._style) if row else None
                row.append(dummy)

    # Group rows by (employee_id, project_account), preserving first-occurrence order
    groups = []      # [(key, [rows])]
    group_keys = []  # parallel list for fast lookup

    for row in split_rows:
        proj_id = row[project_id_col - 1].value
        proj_id_str = str(proj_id).strip() if proj_id is not None else ''

        if proj_id_str not in payment_mapping:
            fatal(f"Error: project_id '{proj_id_str}' in split result has no matching payment account")

        proj_account = payment_mapping[proj_id_str]
        emp_id = row[employee_id_col - 1].value

        group_key = (emp_id, proj_account)

        if group_key in group_keys:
            idx = group_keys.index(group_key)
            groups[idx][1].append(row)
        else:
            group_keys.append(group_key)
            groups.append((group_key, [row]))

    # Merge each group
    merged_rows = []
    for group_key, rows in groups:
        emp_id, proj_account = group_key

        # Start with deep copy of first row
        merged_row = deepcopy(rows[0])

        # Collect distinct project_ids and project_categories
        proj_ids = []
        proj_categories = []
        total_hours = 0.0

        # Initialize splitting column sums
        splitting_sums = {col_idx: 0.0 for col_idx in splitting_col_indices if col_idx}

        for row in rows:
            pid = row[project_id_col - 1].value
            pid_str = str(pid).strip() if pid is not None else ''
            if pid_str and pid_str not in proj_ids:
                proj_ids.append(pid_str)

            if project_category_col:
                cat = row[project_category_col - 1].value
                cat_str = str(cat).strip() if cat is not None else ''
                if cat_str and cat_str not in proj_categories:
                    proj_categories.append(cat_str)

            if project_hours_col:
                hours = row[project_hours_col - 1].value
                try:
                    total_hours += float(hours) if hours is not None else 0.0
                except (ValueError, TypeError):
                    fatal(f"Error: Cannot sum project_hours value '{hours}'")

            # Sum splitting columns
            for col_idx in splitting_col_indices:
                if col_idx:
                    val = row[col_idx - 1].value
                    try:
                        splitting_sums[col_idx] += float(val) if val is not None else 0.0
                    except (ValueError, TypeError):
                        fatal(f"Error: Cannot sum splitting column '{source_headers[col_idx - 1]}' value '{val}'")

        # Set merged values
        merged_row[project_id_col - 1].value = ','.join(proj_ids)
        if project_category_col:
            merged_row[project_category_col - 1].value = ','.join(proj_categories)
        if project_hours_col:
            merged_row[project_hours_col - 1].value = round(total_hours, 2)
        if project_account_col:
            merged_row[project_account_col - 1].value = proj_account

        # Set summed splitting columns
        for col_idx, sum_val in splitting_sums.items():
            merged_row[col_idx - 1].value = round(sum_val, 2)

        merged_rows.append(merged_row)

    return merged_rows


def validate_sheets(config, wb):
    """Validate that required sheets and columns exist, and run pre-processing data checks."""
    source_sheet = config['input']['sheet']['source']['name']
    reference_sheet = config['input']['sheet']['reference']['name']
    payment_sheet = config['input']['sheet']['payment']['name']

    # Check if sheets exist
    if source_sheet not in wb.sheetnames:
        fatal(f"Error: Source sheet '{source_sheet}' does not exist")
    if reference_sheet not in wb.sheetnames:
        fatal(f"Error: Reference sheet '{reference_sheet}' does not exist")
    if payment_sheet not in wb.sheetnames:
        fatal(f"Error: Payment sheet '{payment_sheet}' does not exist")

    source = wb[source_sheet]
    reference = wb[reference_sheet]
    payment = wb[payment_sheet]

    # Get header rows
    source_headers = [cell.value for cell in source[1]]
    reference_headers = [cell.value for cell in reference[1]]
    payment_headers = [cell.value for cell in payment[1]]

    # Validate required columns in source sheet
    required_source_columns = {
        'employee_id': config['input']['sheet']['source']['columns']['employee_id']
    }
    for col_id, col_name in required_source_columns.items():
        if col_name not in source_headers:
            fatal(f"Error: Required column '{col_name}' not found in source sheet")

    # Validate splitting columns in source sheet
    for col_name in config['input']['splitting_columns']:
        if col_name not in source_headers:
            fatal(f"Error: Splitting column '{col_name}' not found in source sheet")

    # Validate required columns in reference sheet
    required_ref_columns = {
        'employee_id': config['input']['sheet']['reference']['columns']['employee_id'],
        'project_id': config['input']['sheet']['reference']['columns']['project_id'],
        'project_category': config['input']['sheet']['reference']['columns']['project_category'],
        'project_hours': config['input']['sheet']['reference']['columns']['project_hours']
    }
    for col_id, col_name in required_ref_columns.items():
        if col_name not in reference_headers:
            fatal(f"Error: Required column '{col_name}' not found in reference sheet")

    # Validate required columns in payment sheet
    required_payment_columns = {
        'project_id': config['input']['sheet']['payment']['columns']['project_id'],
        'project_account': config['input']['sheet']['payment']['columns']['project_account']
    }
    for col_id, col_name in required_payment_columns.items():
        if col_name not in payment_headers:
            fatal(f"Error: Required column '{col_name}' not found in payment sheet")

        # --- Pre-processing data validation ---
    # Collect all errors first, report them together at the end
    errors = []

    ref_employee_id_col = get_column_index(reference_headers,
                                           config['input']['sheet']['reference']['columns']['employee_id'])
    ref_project_id_col = get_column_index(reference_headers,
                                          config['input']['sheet']['reference']['columns']['project_id'])
    payment_project_id_col = get_column_index(payment_headers,
                                              config['input']['sheet']['payment']['columns']['project_id'])
    payment_project_account_col = get_column_index(payment_headers,
                                                    config['input']['sheet']['payment']['columns']['project_account'])
    source_project_id_col = get_column_index(source_headers,
                                              config['input']['sheet']['source']['columns']['project_id'])

    # Check 1: Reference table - no duplicate (employee_id, project_id) pairs
    ref_pairs = set()
    for row in reference.iter_rows(min_row=2):
        emp_id = row[ref_employee_id_col - 1].value
        proj_id = row[ref_project_id_col - 1].value
        pair = (emp_id, proj_id)
        if pair in ref_pairs:
            errors.append(f"Duplicate (employee_id='{emp_id}', project_id='{proj_id}') "
                         f"found in reference sheet '{reference_sheet}'")
        else:
            ref_pairs.add(pair)

    # Check 2 & 3: Payment table - no duplicate project_id + project_account not empty
    payment_mapping = {}
    seen_payment_ids = set()
    for row in payment.iter_rows(min_row=2):
        proj_id = row[payment_project_id_col - 1].value
        proj_account = row[payment_project_account_col - 1].value

        # Skip rows with empty project_id
        if proj_id is None or str(proj_id).strip() == '':
            continue

        proj_id_str = str(proj_id).strip()

        # Check 2: no duplicate project_id
        if proj_id_str in seen_payment_ids:
            errors.append(f"Duplicate project_id '{proj_id_str}' found in "
                         f"payment sheet '{payment_sheet}'")
            continue
        seen_payment_ids.add(proj_id_str)

        # Check 3: project_account must not be empty
        if proj_account is None or str(proj_account).strip() == '':
            errors.append(f"project_id '{proj_id_str}' has empty project_account in "
                         f"payment sheet '{payment_sheet}'")
            continue

        payment_mapping[proj_id_str] = str(proj_account).strip()

    # Check 4: Reference table - all project_id values must exist in payment
    ref_missing_pids = set()
    for row in reference.iter_rows(min_row=2):
        proj_id = row[ref_project_id_col - 1].value
        if proj_id is not None and str(proj_id).strip() != '':
            proj_id_str = str(proj_id).strip()
            if proj_id_str not in payment_mapping:
                ref_missing_pids.add(proj_id_str)
    for pid in sorted(ref_missing_pids):
        errors.append(f"project_id '{pid}' in reference sheet '{reference_sheet}' "
                     f"has no matching record in payment sheet '{payment_sheet}'")

    # Check 5: Source table - rows without reference match (not split) must have
    #           their project_id in payment
    ref_employee_ids = set()
    for row in reference.iter_rows(min_row=2):
        emp_id = row[ref_employee_id_col - 1].value
        if emp_id is not None:
            ref_employee_ids.add(emp_id)

    src_employee_id_col = get_column_index(source_headers,
                                           config['input']['sheet']['source']['columns']['employee_id'])
    source_missing_pids = set()
    if source_project_id_col:
        for row in source.iter_rows(min_row=2):
            emp_id = row[src_employee_id_col - 1].value
            # Only check rows that won't be split (no reference match)
            if emp_id in ref_employee_ids:
                continue
            proj_id = row[source_project_id_col - 1].value
            if proj_id is not None and str(proj_id).strip() != '':
                proj_id_str = str(proj_id).strip()
                if proj_id_str not in payment_mapping:
                    source_missing_pids.add(proj_id_str)
    for pid in sorted(source_missing_pids):
        errors.append(f"project_id '{pid}' in source sheet '{source_sheet}' "
                     f"has no matching record in payment sheet '{payment_sheet}'")

    # Report all collected errors at once
    if errors:
        error_msg = "Validation errors found:\n" + "\n".join(f"  - {e}" for e in errors)
        fatal(error_msg)

    return source, reference, source_headers, reference_headers, payment_mapping

def process_excel(config):
    """Process Excel file according to configuration."""
    input_path = config['input']['path']
    output_path = config['output']['path']
    result_sheet = config['output']['sheet']['result']['name']

    # Check if input file exists
    if not os.path.exists(input_path):
        fatal(f"Error: Input file '{input_path}' does not exist")

    try:
        # Load the workbook
        wb = load_workbook(input_path)
        
        # Validate sheets and columns
        source, reference, source_headers, reference_headers, payment_mapping = validate_sheets(config, wb)
        
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

        # Ensure project_account column exists in source_headers for downstream lookups
        project_account_name = config['input']['sheet']['source']['columns'].get('project_account')
        if project_account_name and get_column_index(source_headers, project_account_name) is None:
            new_col = len(source_headers) + 1
            header_cell = result.cell(row=1, column=new_col)
            header_cell.value = project_account_name
            source_headers.append(project_account_name)

        # Process data rows
        current_row = 2
        reference_rows = list(reference.iter_rows(min_row=2))  # Convert iterator to list
        for row in source.iter_rows(min_row=2):
            split_result_rows = split_row(row, reference_rows, source_headers, reference_headers, config)
            # Merge split rows by payment account
            merged_rows = merge_rows_by_account(split_result_rows, source_headers, payment_mapping, config)
            for result_row in merged_rows:
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
        traceback.print_exc()
        fatal(f"Error: Invalid Excel file '{input_path}'")
    except Exception as e:
        traceback.print_exc()
        fatal(f"Error processing Excel file: {e}")

def fatal(message):
    print(message)
    try:
        input("执行失败，按回车键退出")
    except EOFError:
        pass
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

    input("执行成功，按回车键退出")


if __name__ == '__main__':
    main() 