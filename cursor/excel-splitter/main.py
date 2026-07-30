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
        try:
            ref_hours = float(ref_row[ref_hours_col - 1].value)
        except (ValueError, TypeError):
            fatal(f"Error: Non-numeric project_hours '{ref_row[ref_hours_col - 1].value}' "
                  f"in reference sheet for employee_id='{ref_employee_id}'")
        total_ref_hours += ref_hours

    if total_ref_hours == 0:
        # 如果总工时为0，直接复制原行
        return [list(source_row)]

    # Split the row
    remain_row = deepcopy(source_row)
    result_rows = []
    for i, ref_row in enumerate(matching_ref_rows):
        ref_hours_col = get_column_index(reference_headers, config['input']['sheet']['reference']['columns']['project_hours'])
        try:
            ref_hours = float(ref_row[ref_hours_col - 1].value)
        except (ValueError, TypeError):
            fatal(f"Error: Non-numeric project_hours '{ref_row[ref_hours_col - 1].value}' "
                  f"in reference sheet for employee_id='{employee_id}'")
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

    splitting_col_indices = list(dict.fromkeys(
        get_column_index(source_headers, col_name)
        for col_name in config['input']['splitting_columns']
        if get_column_index(source_headers, col_name) is not None
    ))

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


def validate_sheets(config, wb, payment_configured=True):
    """Validate that required sheets and columns exist, and run pre-processing data checks."""
    source_sheet = config['input']['sheet']['source']['name']
    reference_sheet = config['input']['sheet']['reference']['name']

    # Check if sheets exist
    if source_sheet not in wb.sheetnames:
        fatal(f"Error: Source sheet '{source_sheet}' does not exist")
    if reference_sheet not in wb.sheetnames:
        fatal(f"Error: Reference sheet '{reference_sheet}' does not exist")

    source = wb[source_sheet]
    reference = wb[reference_sheet]

    # Get header rows
    source_headers = [cell.value for cell in source[1]]
    reference_headers = [cell.value for cell in reference[1]]

    # Payment sheet is optional
    if payment_configured:
        payment_sheet = config['input']['sheet']['payment']['name']
        if payment_sheet not in wb.sheetnames:
            fatal(f"Error: Payment sheet '{payment_sheet}' does not exist")
        payment = wb[payment_sheet]
        payment_headers = [cell.value for cell in payment[1]]
    else:
        payment = None
        payment_headers = []

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

    # Validate required columns in payment sheet (only if configured)
    if payment_configured:
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
    ref_hours_col = get_column_index(reference_headers,
                                     config['input']['sheet']['reference']['columns']['project_hours'])

    source_project_id_col = get_column_index(source_headers,
                                              config['input']['sheet']['source']['columns']['project_id'])

    # Payment-related column indices (only used if payment_configured)
    payment_mapping = {}
    if payment_configured:
        payment_project_id_col = get_column_index(payment_headers,
                                                  config['input']['sheet']['payment']['columns']['project_id'])
        payment_project_account_col = get_column_index(payment_headers,
                                                        config['input']['sheet']['payment']['columns']['project_account'])

    # Check 1: Reference table - no duplicate (employee_id, project_id) pairs
    ref_pairs = set()
    reported_ref_duplicates = set()
    for row in reference.iter_rows(min_row=2):
        emp_id = row[ref_employee_id_col - 1].value
        proj_id = row[ref_project_id_col - 1].value
        pair = (emp_id, proj_id)
        if pair in ref_pairs:
            if pair not in reported_ref_duplicates:
                errors.append(f"Duplicate (employee_id='{emp_id}', project_id='{proj_id}') "
                             f"found in reference sheet '{reference_sheet}'")
                reported_ref_duplicates.add(pair)
        else:
            ref_pairs.add(pair)

    # Payment checks (only if payment is configured)
    if payment_configured:
        # Check 2 & 3: Payment table - no duplicate project_id + project_account not empty
        seen_payment_ids = set()
        reported_duplicates = set()
        for row in payment.iter_rows(min_row=2):
            proj_id = row[payment_project_id_col - 1].value
            proj_account = row[payment_project_account_col - 1].value

            # Skip rows with empty project_id
            if proj_id is None or str(proj_id).strip() == '':
                continue

            proj_id_str = str(proj_id).strip()

            # Check 2: no duplicate project_id (report each duplicate ID only once)
            if proj_id_str in seen_payment_ids:
                if proj_id_str not in reported_duplicates:
                    errors.append(f"Duplicate project_id '{proj_id_str}' found in "
                                 f"payment sheet '{payment_sheet}'")
                    reported_duplicates.add(proj_id_str)
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

    # --- New data quality pre-checks (6-10) ---

    src_employee_id_col = get_column_index(source_headers,
                                           config['input']['sheet']['source']['columns']['employee_id'])

    # Check 6: None/empty employee_id in reference rows
    for row_num, row in enumerate(reference.iter_rows(min_row=2), start=2):
        emp_id = row[ref_employee_id_col - 1].value
        if emp_id is None or (isinstance(emp_id, str) and emp_id.strip() == ''):
            errors.append(f"Empty employee_id in reference sheet '{reference_sheet}' row {row_num}")
            break  # One error is enough

    # Check 7: None/empty employee_id in source rows
    for row_num, row in enumerate(source.iter_rows(min_row=2), start=2):
        emp_id = row[src_employee_id_col - 1].value
        if emp_id is None or (isinstance(emp_id, str) and emp_id.strip() == ''):
            errors.append(f"Empty employee_id in source sheet '{source_sheet}' row {row_num}")
            break

    # Check 8: Non-numeric project_hours in reference
    for row_num, row in enumerate(reference.iter_rows(min_row=2), start=2):
        hours_val = row[ref_hours_col - 1].value
        if hours_val is not None:
            try:
                float(hours_val)
            except (ValueError, TypeError):
                emp_id = row[ref_employee_id_col - 1].value
                proj_id = row[ref_project_id_col - 1].value
                errors.append(f"Non-numeric project_hours '{hours_val}' in reference sheet "
                             f"'{reference_sheet}' row {row_num} "
                             f"(employee_id='{emp_id}', project_id='{proj_id}')")

    # Check 9: Negative project_hours in reference
    for row_num, row in enumerate(reference.iter_rows(min_row=2), start=2):
        hours_val = row[ref_hours_col - 1].value
        if hours_val is not None:
            try:
                if float(hours_val) < 0:
                    emp_id = row[ref_employee_id_col - 1].value
                    proj_id = row[ref_project_id_col - 1].value
                    errors.append(f"Negative project_hours '{hours_val}' in reference sheet "
                                 f"'{reference_sheet}' row {row_num} "
                                 f"(employee_id='{emp_id}', project_id='{proj_id}')")
            except (ValueError, TypeError):
                pass  # Already caught by Check 8

    # Check 10: employee_id type mismatch between sheets
    ref_id_types = set()
    src_id_types = set()
    for row in reference.iter_rows(min_row=2):
        emp_id = row[ref_employee_id_col - 1].value
        if emp_id is not None and not (isinstance(emp_id, str) and emp_id.strip() == ''):
            ref_id_types.add(type(emp_id).__name__)
    for row in source.iter_rows(min_row=2):
        emp_id = row[src_employee_id_col - 1].value
        if emp_id is not None and not (isinstance(emp_id, str) and emp_id.strip() == ''):
            src_id_types.add(type(emp_id).__name__)
    all_id_types = ref_id_types | src_id_types
    if len(all_id_types) > 1:
        types_str = ', '.join(sorted(all_id_types))
        errors.append(f"employee_id type mismatch: found types [{types_str}] across "
                     f"source and reference sheets. All employee_id values should be the same type.")

    # Report all collected errors at once
    if errors:
        error_msg = "Validation errors found:\n" + "\n".join(f"  - {e}" for e in errors)
        fatal(error_msg)

    return source, reference, source_headers, reference_headers, payment_mapping


def verify_output(config, source_headers):
    """Verify the output file after processing. Returns a list of error messages."""
    errors = []
    output_path = config['output']['path']
    result_sheet_name = config['output']['sheet']['result']['name']
    source_sheet_name = config['input']['sheet']['source']['name']
    splitting_columns = config['input']['splitting_columns']

    splitting_columns = list(dict.fromkeys(config['input']['splitting_columns']))

    if not os.path.exists(output_path):
        errors.append(f"Output file '{output_path}' does not exist")
        return errors

    try:
        wb = load_workbook(output_path)
    except Exception as e:
        errors.append(f"Cannot open output file '{output_path}': {e}")
        return errors

    # Check result sheet exists
    if result_sheet_name not in wb.sheetnames:
        errors.append(f"Result sheet '{result_sheet_name}' not found in output file")
        wb.close()
        return errors

    result = wb[result_sheet_name]

    # Check source sheet exists in output (output is a copy of input)
    if source_sheet_name not in wb.sheetnames:
        errors.append(f"Source sheet '{source_sheet_name}' not found in output file")
        wb.close()
        return errors

    source = wb[source_sheet_name]
    result_headers = [cell.value for cell in result[1]]
    source_out_headers = [cell.value for cell in source[1]]

    # Check no empty rows in result
    for i, row in enumerate(result.iter_rows(min_row=2), start=2):
        if all(cell.value is None for cell in row):
            errors.append(f"Empty row {i} in result sheet '{result_sheet_name}'")

    # Check splitting columns: numeric, non-negative in result
    for col_name in splitting_columns:
        col_idx = get_column_index(result_headers, col_name)
        if col_idx is None:
            errors.append(f"Splitting column '{col_name}' not found in result headers")
            continue
        for i, row in enumerate(result.iter_rows(min_row=2), start=2):
            val = row[col_idx - 1].value
            if val is not None:
                try:
                    fval = float(val)
                    if fval < -0.001:  # Small tolerance for rounding
                        errors.append(f"Negative value {fval} in '{col_name}' at result row {i}")
                except (ValueError, TypeError):
                    errors.append(f"Non-numeric value '{val}' in '{col_name}' at result row {i}")

    # Grand total consistency: sum of each splitting column in result should
    # equal the sum in source (within rounding tolerance)
    for col_name in splitting_columns:
        src_col = get_column_index(source_out_headers, col_name)
        res_col = get_column_index(result_headers, col_name)
        if not src_col or not res_col:
            continue

        src_sum = 0.0
        for row in source.iter_rows(min_row=2):
            val = row[src_col - 1].value
            if val is not None:
                try:
                    src_sum += float(val)
                except (ValueError, TypeError):
                    pass  # Non-numeric source values were caught by pre-checks

        res_sum = 0.0
        for row in result.iter_rows(min_row=2):
            val = row[res_col - 1].value
            if val is not None:
                try:
                    res_sum += float(val)
                except (ValueError, TypeError):
                    pass  # Already caught above

        if abs(res_sum - src_sum) > 0.001:
            errors.append(f"Total mismatch for '{col_name}': "
                         f"source sum={src_sum:.2f}, result sum={res_sum:.2f}")

    wb.close()
    return errors


def validate_config(config):
    """Validate configuration structure. Returns True if payment sheet is configured."""
    errors = []

    if config is None:
        fatal("Error: Configuration is empty")

    # Check input section
    inp = config.get('input')
    if inp is None:
        errors.append("Missing 'input' section in configuration")
    else:
        if 'path' not in inp or not isinstance(inp['path'], str) or inp['path'].strip() == '':
            errors.append("Missing or invalid 'input.path' in configuration")

        sheets = inp.get('sheet')
        if sheets is None:
            errors.append("Missing 'input.sheet' section in configuration")
        else:
            # Source sheet
            source = sheets.get('source')
            if source is None:
                errors.append("Missing 'input.sheet.source' in configuration")
            else:
                if 'name' not in source or not isinstance(source['name'], str) or source['name'].strip() == '':
                    errors.append("Missing or invalid 'input.sheet.source.name' in configuration")
                if 'columns' not in source:
                    errors.append("Missing 'input.sheet.source.columns' in configuration")
                elif 'employee_id' not in source['columns']:
                    errors.append("Missing 'input.sheet.source.columns.employee_id' in configuration")

            # Reference sheet
            ref = sheets.get('reference')
            if ref is None:
                errors.append("Missing 'input.sheet.reference' in configuration")
            else:
                if 'name' not in ref or not isinstance(ref['name'], str) or ref['name'].strip() == '':
                    errors.append("Missing or invalid 'input.sheet.reference.name' in configuration")
                if 'columns' not in ref:
                    errors.append("Missing 'input.sheet.reference.columns' in configuration")
                else:
                    for col in ['employee_id', 'project_id', 'project_category', 'project_hours']:
                        if col not in ref['columns']:
                            errors.append(f"Missing 'input.sheet.reference.columns.{col}' in configuration")

            # Payment sheet (optional)
            payment_configured = False
            if 'payment' in sheets:
                pay = sheets['payment']
                if 'name' in pay and isinstance(pay['name'], str) and pay['name'].strip() != '' \
                   and 'columns' in pay \
                   and 'project_id' in pay['columns'] \
                   and 'project_account' in pay['columns']:
                    payment_configured = True
                else:
                    errors.append("Missing or incomplete 'input.sheet.payment' configuration")

            # Conflict check: project_account in source columns but no payment
            source_cols = sheets.get('source', {}).get('columns', {})
            if 'project_account' in source_cols and not payment_configured:
                errors.append("'project_account' is specified in source columns "
                              "but payment sheet is not properly configured")

        # splitting_columns
        split_cols = inp.get('splitting_columns')
        if split_cols is None:
            errors.append("Missing 'input.splitting_columns' in configuration")
        elif not isinstance(split_cols, list) or len(split_cols) == 0:
            errors.append("'input.splitting_columns' must be a non-empty list")
        else:
            seen = set()
            for col in split_cols:
                if col in seen:
                    errors.append(f"Duplicate entry '{col}' in 'input.splitting_columns'")
                else:
                    seen.add(col)

    # Check output section
    out = config.get('output')
    if out is None:
        errors.append("Missing 'output' section in configuration")
    else:
        if 'path' not in out or not isinstance(out['path'], str) or out['path'].strip() == '':
            errors.append("Missing or invalid 'output.path' in configuration")
        out_sheet = out.get('sheet')
        if out_sheet is None:
            errors.append("Missing 'output.sheet' in configuration")
        elif 'result' not in out_sheet:
            errors.append("Missing 'output.sheet.result' in configuration")
        elif 'name' not in out_sheet['result'] or not isinstance(out_sheet['result']['name'], str) \
                or out_sheet['result']['name'].strip() == '':
            errors.append("Missing or invalid 'output.sheet.result.name' in configuration")

    if errors:
        error_msg = "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        fatal(error_msg)

    return payment_configured


def process_excel(config):
    """Process Excel file according to configuration."""
    # Validate config structure first
    payment_configured = validate_config(config)

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
        source, reference, source_headers, reference_headers, payment_mapping = \
            validate_sheets(config, wb, payment_configured)

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

        # Ensure project_account column exists in source_headers (only if payment is configured)
        if payment_configured:
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
            # Merge split rows by payment account (only if payment is configured)
            if payment_configured:
                merged_rows = merge_rows_by_account(split_result_rows, source_headers, payment_mapping, config)
            else:
                merged_rows = split_result_rows
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

        # Verify output after save
        output_errors = verify_output(config, source_headers)
        if output_errors:
            error_msg = "Output verification errors:\n" + "\n".join(f"  - {e}" for e in output_errors)
            fatal(error_msg)
        
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