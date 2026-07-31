#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import time
import traceback
import yaml
from openpyxl import load_workbook
from openpyxl.cell import Cell
from openpyxl.utils.exceptions import InvalidFileException
from copy import copy

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

def split_row(source_row, ref_by_employee, source_headers, reference_headers, config,
              source_col_map, ref_col_map, splitting_col_set):
    """Split a row based on reference data."""
    # Precompute all column indices once using O(1) map lookups
    employee_id_col = source_col_map[config['input']['sheet']['source']['columns']['employee_id']]
    ref_hours_col = ref_col_map[config['input']['sheet']['reference']['columns']['project_hours']]
    project_id_col = source_col_map.get(config['input']['sheet']['source']['columns']['project_id'])
    project_category_col = source_col_map.get(config['input']['sheet']['source']['columns']['project_category'])
    project_hours_col = source_col_map.get(config['input']['sheet']['source']['columns']['project_hours'])
    ref_project_id_col = ref_col_map.get(config['input']['sheet']['reference']['columns']['project_id'])
    ref_project_category_col = ref_col_map.get(config['input']['sheet']['reference']['columns']['project_category'])
    ref_project_hours_col = ref_col_map.get(config['input']['sheet']['reference']['columns']['project_hours'])

    employee_id = source_row[employee_id_col - 1].value

    # O(1) lookup in pre-indexed reference dict
    matching_ref_rows = ref_by_employee.get(employee_id, [])

    if not matching_ref_rows:
        # No matching reference rows, copy source row as is
        return [list(source_row)]

    # 计算reference表中匹配行的总工时
    total_ref_hours = 0
    for ref_row in matching_ref_rows:
        try:
            ref_hours = float(ref_row[ref_hours_col - 1].value)
        except (ValueError, TypeError):
            fatal(f"Error: Non-numeric project_hours '{ref_row[ref_hours_col - 1].value}' "
                  f"in reference sheet for employee_id='{employee_id}'")
        total_ref_hours += ref_hours

    if total_ref_hours == 0:
        # 如果总工时为0，直接复制原行
        return [list(source_row)]

    # Split the row
    # Track remaining values for each splitting column (avoid deepcopy of Cell objects)
    remain_values = []
    for j, cell in enumerate(source_row):
        if cell.value is not None and cell.column in splitting_col_set:
            try:
                remain_values.append(float(cell.value))
            except (ValueError, TypeError):
                fatal(f"Error: 无法拆分'{source_headers[j]}:{source_row[j].value}'")
        else:
            remain_values.append(0.0)  # placeholder for non-splitting columns

    result_rows = []
    for i, ref_row in enumerate(matching_ref_rows):
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
            if cell.value is not None and cell.column in splitting_col_set:
                # Split numeric values
                try:
                    if i < len(matching_ref_rows) - 1:
                        new_cell.value = round(float(cell.value) * ratio, 2)
                        remain_values[j] -= new_cell.value
                    else:
                        new_cell.value = remain_values[j]
                except (ValueError, TypeError):
                    fatal(f"Error: 无法拆分'{source_headers[j]}:{source_row[j].value}'")
            new_row.append(new_cell)

        # 只更新project_id, project_category, project_hours这三列
        if project_id_col and ref_project_id_col:
            new_row[project_id_col - 1].value = ref_row[ref_project_id_col - 1].value

        if project_category_col and ref_project_category_col:
            new_row[project_category_col - 1].value = ref_row[ref_project_category_col - 1].value

        if project_hours_col and ref_project_hours_col:
            new_row[project_hours_col - 1].value = ref_row[ref_project_hours_col - 1].value

        result_rows.append(new_row)

    return result_rows

def merge_rows_by_account(split_rows, source_headers, payment_mapping, config,
                          source_col_map, splitting_col_list):
    """Merge split result rows by (employee_id, payment_account)."""
    if not split_rows:
        return []

    # Precompute all column indices once using O(1) map lookups
    employee_id_col = source_col_map.get(config['input']['sheet']['source']['columns']['employee_id'])
    project_id_col = source_col_map.get(config['input']['sheet']['source']['columns']['project_id'])
    project_category_col = source_col_map.get(config['input']['sheet']['source']['columns']['project_category'])
    project_hours_col = source_col_map.get(config['input']['sheet']['source']['columns']['project_hours'])
    payment_account_col = source_col_map.get(config['input']['sheet']['source']['columns']['payment_account'])
    employer_name_col = source_col_map.get(config['input']['sheet']['source']['columns']['employer_name'])

    splitting_col_indices = splitting_col_list  # Already precomputed


    # Ensure all split rows have enough cells for payment_account column
    # (source sheet may not have the payment_account column)
    max_cols = len(source_headers)
    if payment_account_col:
        for row in split_rows:
            while len(row) < max_cols:
                dummy = Cell(None, column=len(row) + 1)
                dummy.value = None
                dummy._style = copy(row[0]._style) if row else None
                row.append(dummy)

    # Group rows by (employee_id, payment_account), preserving first-occurrence order
    # Dict maintains insertion order (Python 3.7+)
    groups = {}  # group_key -> [rows]

    for row in split_rows:
        proj_id = row[project_id_col - 1].value
        proj_id_str = str(proj_id).strip() if proj_id is not None else ''
        employer_name = row[employer_name_col - 1].value if employer_name_col else None
        employer_name_str = str(employer_name).strip() if employer_name is not None else ''

        # Use composite key (employer_name, project_id) to look up payment_account
        lookup_key = (employer_name_str, proj_id_str)
        if lookup_key not in payment_mapping:
            fatal(f"Error: (employer_name='{employer_name_str}', project_id='{proj_id_str}') "
                  f"in split result has no matching payment account")

        proj_account = payment_mapping[lookup_key]
        emp_id = row[employee_id_col - 1].value

        group_key = (emp_id, proj_account)

        if group_key in groups:
            groups[group_key].append(row)
        else:
            groups[group_key] = [row]

    # Merge each group
    merged_rows = []
    for group_key, rows in groups.items():
        emp_id, proj_account = group_key

        # Start with shallow copy of first row (list of cells)
        merged_row = list(rows[0])

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
        if payment_account_col:
            merged_row[payment_account_col - 1].value = proj_account

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
            'payment_account': config['input']['sheet']['payment']['columns']['payment_account']
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
        payment_payment_account_col = get_column_index(payment_headers,
                                                        config['input']['sheet']['payment']['columns']['payment_account'])
        payment_employer_name_col = get_column_index(payment_headers,
                                                      config['input']['sheet']['payment']['columns']['employer_name'])

    # --- Payment checks (only if payment is configured) ---
    # Build payment_mapping and payment_project_ids before reference/source scans
    payment_project_ids = set()
    ref_employee_ids = set()
    if payment_configured:
        # Check 2 & 3: Payment table - no duplicate (employer_name, project_id) + payment_account not empty
        seen_payment_pairs = set()
        reported_duplicates = set()
        for row in payment.iter_rows(min_row=2):
            proj_id = row[payment_project_id_col - 1].value
            proj_account = row[payment_payment_account_col - 1].value
            employer_name = row[payment_employer_name_col - 1].value

            # Skip rows with empty project_id or empty employer_name
            if proj_id is None or str(proj_id).strip() == '':
                continue
            if employer_name is None or str(employer_name).strip() == '':
                continue

            proj_id_str = str(proj_id).strip()
            employer_name_str = str(employer_name).strip()

            # Check 2: no duplicate (employer_name, project_id) (report each duplicate pair only once)
            pair = (employer_name_str, proj_id_str)
            if pair in seen_payment_pairs:
                if pair not in reported_duplicates:
                    errors.append(f"Duplicate (employer_name='{employer_name_str}', project_id='{proj_id_str}') "
                                 f"found in payment sheet '{payment_sheet}'")
                    reported_duplicates.add(pair)
                continue
            seen_payment_pairs.add(pair)

            # Check 3: payment_account must not be empty
            if proj_account is None or str(proj_account).strip() == '':
                errors.append(f"project_id '{proj_id_str}' has empty payment_account in "
                             f"payment sheet '{payment_sheet}'")
                continue

            payment_mapping[pair] = str(proj_account).strip()

        # Build set of all project_ids in payment for Check 4 partial check
        payment_project_ids = set(pid for (_, pid) in payment_mapping.keys())

    # --- Consolidated single-pass scan of reference sheet ---
    # Checks 1, 4, 6, 8, 9, and partial 10 (type collection)
    ref_pairs = set()
    reported_ref_duplicates = set()
    ref_missing_pids = set() if payment_configured else None
    reported_empty_ref_id = False
    ref_id_types = set()

    for row_num, row in enumerate(reference.iter_rows(min_row=2), start=2):
        emp_id = row[ref_employee_id_col - 1].value
        proj_id = row[ref_project_id_col - 1].value
        hours_val = row[ref_hours_col - 1].value

        # Check 6: empty employee_id
        if not reported_empty_ref_id and (emp_id is None or
           (isinstance(emp_id, str) and str(emp_id).strip() == '')):
            errors.append(f"Empty employee_id in reference sheet '{reference_sheet}' row {row_num}")
            reported_empty_ref_id = True

        # Check 10: type info (skip if empty)
        if emp_id is not None and not (isinstance(emp_id, str) and str(emp_id).strip() == ''):
            ref_id_types.add(type(emp_id).__name__)

        # Build ref_employee_ids for Check 5 (source scan)
        if payment_configured and emp_id is not None:
            ref_employee_ids.add(emp_id)

        # Check 1: duplicate (employee_id, project_id)
        if emp_id is not None and proj_id is not None:
            pair = (emp_id, proj_id)
            if pair in ref_pairs:
                if pair not in reported_ref_duplicates:
                    errors.append(f"Duplicate (employee_id='{emp_id}', project_id='{proj_id}') "
                                  f"found in reference sheet '{reference_sheet}'")
                    reported_ref_duplicates.add(pair)
            else:
                ref_pairs.add(pair)

        # Check 4: project_id in payment (only if payment configured)
        if payment_configured and proj_id is not None and str(proj_id).strip() != '':
            proj_id_str = str(proj_id).strip()
            if proj_id_str not in payment_project_ids:
                ref_missing_pids.add(proj_id_str)

        # Checks 8 and 9: non-numeric and negative hours
        if hours_val is not None:
            try:
                hours_float = float(hours_val)
                if hours_float < 0:
                    errors.append(f"Negative project_hours '{hours_val}' in reference sheet "
                                  f"'{reference_sheet}' row {row_num} "
                                  f"(employee_id='{emp_id}', project_id='{proj_id}')")
            except (ValueError, TypeError):
                errors.append(f"Non-numeric project_hours '{hours_val}' in reference sheet "
                              f"'{reference_sheet}' row {row_num} "
                              f"(employee_id='{emp_id}', project_id='{proj_id}')")

    # Report Check 4 errors after reference scan
    if payment_configured and ref_missing_pids:
        for pid in sorted(ref_missing_pids):
            errors.append(f"project_id '{pid}' in reference sheet '{reference_sheet}' "
                         f"has no matching record in payment sheet '{payment_sheet}'")

    # --- Consolidated single-pass scan of source sheet ---
    # Checks 5, 7, and partial 10 (type collection)
    src_employee_id_col = get_column_index(source_headers,
                                           config['input']['sheet']['source']['columns']['employee_id'])
    reported_empty_src_id = False
    src_id_types = set()
    source_missing_pairs = set() if payment_configured else None

    if payment_configured:
        src_employer_name_col = get_column_index(source_headers,
                                                  config['input']['sheet']['source']['columns']['employer_name'])

    for row_num, row in enumerate(source.iter_rows(min_row=2), start=2):
        emp_id = row[src_employee_id_col - 1].value

        # Check 7: empty employee_id
        if not reported_empty_src_id and (emp_id is None or
           (isinstance(emp_id, str) and str(emp_id).strip() == '')):
            errors.append(f"Empty employee_id in source sheet '{source_sheet}' row {row_num}")
            reported_empty_src_id = True

        # Check 10: type info
        if emp_id is not None and not (isinstance(emp_id, str) and str(emp_id).strip() == ''):
            src_id_types.add(type(emp_id).__name__)

        # Check 5: non-split rows must have payment mapping
        if payment_configured and source_project_id_col and src_employer_name_col:
            if emp_id in ref_employee_ids:
                continue  # Will be split; source project_id replaced
            proj_id = row[source_project_id_col - 1].value
            employer_name = row[src_employer_name_col - 1].value
            if proj_id is not None and str(proj_id).strip() != '' \
               and employer_name is not None and str(employer_name).strip() != '':
                pair = (str(employer_name).strip(), str(proj_id).strip())
                if pair not in payment_mapping:
                    source_missing_pairs.add(pair)

    # Report Check 5 errors after source scan
    if payment_configured and source_missing_pairs:
        for pair in sorted(source_missing_pairs):
            errors.append(f"(employer_name='{pair[0]}', project_id='{pair[1]}') in source sheet "
                         f"'{source_sheet}' has no matching record in payment sheet '{payment_sheet}'")

    # Check 10: employee_id type mismatch between sheets
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
    # Precompute column indices for all splitting columns
    result_col_map_verify = {}
    for col_name in splitting_columns:
        col_idx = get_column_index(result_headers, col_name)
        if col_idx is None:
            errors.append(f"Splitting column '{col_name}' not found in result headers")
        else:
            result_col_map_verify[col_name] = col_idx

    # Single pass through result: validate numeric/non-negative for all splitting columns
    for i, row in enumerate(result.iter_rows(min_row=2), start=2):
        for col_name, col_idx in result_col_map_verify.items():
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
    # Precompute column indices
    src_col_map_verify = {}
    res_col_map_verify = {}
    for col_name in splitting_columns:
        src_idx = get_column_index(source_out_headers, col_name)
        res_idx = get_column_index(result_headers, col_name)
        if src_idx and res_idx:
            src_col_map_verify[col_name] = src_idx
            res_col_map_verify[col_name] = res_idx

    if src_col_map_verify:
        # Single pass through source: sum all splitting columns
        src_sums = {col_name: 0.0 for col_name in src_col_map_verify}
        for row in source.iter_rows(min_row=2):
            for col_name, col_idx in src_col_map_verify.items():
                val = row[col_idx - 1].value
                if val is not None:
                    try:
                        src_sums[col_name] += float(val)
                    except (ValueError, TypeError):
                        pass  # Non-numeric source values were caught by pre-checks

        # Single pass through result: sum all splitting columns
        res_sums = {col_name: 0.0 for col_name in res_col_map_verify}
        for row in result.iter_rows(min_row=2):
            for col_name, col_idx in res_col_map_verify.items():
                val = row[col_idx - 1].value
                if val is not None:
                    try:
                        res_sums[col_name] += float(val)
                    except (ValueError, TypeError):
                        pass  # Already caught above

        # Compare each column's sums
        for col_name in splitting_columns:
            if col_name not in src_col_map_verify or col_name not in res_col_map_verify:
                continue
            src_sum = src_sums.get(col_name, 0.0)
            res_sum = res_sums.get(col_name, 0.0)
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
                   and 'payment_account' in pay['columns'] \
                   and 'employer_name' in pay['columns']:
                    payment_configured = True
                else:
                    errors.append("Missing or incomplete 'input.sheet.payment' configuration")

            # Conflict check: payment_account or employer_name in source columns but no payment
            source_cols = sheets.get('source', {}).get('columns', {})
            if 'payment_account' in source_cols and not payment_configured:
                errors.append("'payment_account' is specified in source columns "
                              "but payment sheet is not properly configured")
            if 'employer_name' in source_cols and not payment_configured:
                errors.append("'employer_name' is specified in source columns "
                              "but payment sheet is not properly configured")
            if payment_configured and 'employer_name' not in source_cols:
                errors.append("'employer_name' is required in source columns "
                              "when payment sheet is configured")

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
        print(f"正在加载工作簿: {input_path}")
        wb = load_workbook(input_path)
        print("工作簿加载完成")
        
        # Validate sheets and columns
        source, reference, source_headers, reference_headers, payment_mapping = \
            validate_sheets(config, wb, payment_configured)
        print("验证完成")

        # Create a new workbook for output
        output_wb = load_workbook(input_path)

        # If result sheet exists, remove it
        if result_sheet in output_wb.sheetnames:
            output_wb.remove(output_wb[result_sheet])

        keep_style = config.get('keep_style', True)

        # Create new sheet
        result = output_wb.create_sheet(result_sheet)

        # Copy headers
        for cell in source[1]:
            new_cell = result.cell(row=1, column=cell.column)
            new_cell.value = cell.value
            if keep_style:
                copy_cell_style(cell, new_cell)

        # Ensure payment_account column exists in source_headers (only if payment is configured)
        if payment_configured:
            payment_account_name = config['input']['sheet']['source']['columns'].get('payment_account')
            if payment_account_name and get_column_index(source_headers, payment_account_name) is None:
                new_col = len(source_headers) + 1
                header_cell = result.cell(row=1, column=new_col)
                header_cell.value = payment_account_name
                source_headers.append(payment_account_name)

        # Precompute column name -> index maps for O(1) lookups (after source_headers is finalized)
        source_col_map = {name: idx + 1 for idx, name in enumerate(source_headers)}
        ref_col_map = {name: idx + 1 for idx, name in enumerate(reference_headers)}

        # Precompute splitting column indices as set (fast membership test in split_row)
        # and ordered list (for merge_rows_by_account)
        splitting_col_set = set()
        splitting_col_list = []
        for col_name in config['input']['splitting_columns']:
            idx = source_col_map.get(col_name)
            if idx is not None:
                splitting_col_set.add(idx)
                if idx not in splitting_col_list:
                    splitting_col_list.append(idx)

        # Process data rows
        current_row = 2
        reference_rows = list(reference.iter_rows(min_row=2))  # Convert iterator to list

        # Pre-index reference rows by employee_id for O(1) lookup
        ref_employee_id_col = ref_col_map[config['input']['sheet']['reference']['columns']['employee_id']]
        ref_by_employee = {}
        for ref_row in reference_rows:
            emp_id = ref_row[ref_employee_id_col - 1].value
            if emp_id not in ref_by_employee:
                ref_by_employee[emp_id] = []
            ref_by_employee[emp_id].append(ref_row)

        total_source_rows = source.max_row - 1  # Subtract header row
        total_reference_rows = len(reference_rows)
        print(f"开始处理数据，共 {total_source_rows} 行（参考表 {total_reference_rows} 行，{len(ref_by_employee)} 个员工）")
        progress_interval = config.get('progress_interval', 100)
        row_counter = 0
        t_total_start = time.time()
        t_split_total = 0.0
        t_merge_total = 0.0
        t_write_total = 0.0
        for row in source.iter_rows(min_row=2):
            row_counter += 1
            if row_counter % progress_interval == 0 or row_counter == 1:
                elapsed = time.time() - t_total_start
                rate = row_counter / elapsed if elapsed > 0 else 0
                eta = (total_source_rows - row_counter) / rate if rate > 0 else 0
                print(f"正在处理第 {row_counter}/{total_source_rows} 行 (已耗时 {elapsed:.0f}s, 速度 {rate:.1f} 行/秒, 预计剩余 {eta:.0f}s)...")

            t0 = time.time()
            split_result_rows = split_row(row, ref_by_employee, source_headers, reference_headers, config,
                                           source_col_map, ref_col_map, splitting_col_set)
            t_split_total += time.time() - t0

            # Merge split rows by payment account (only if payment is configured)
            if payment_configured:
                t0 = time.time()
                merged_rows = merge_rows_by_account(split_result_rows, source_headers, payment_mapping, config,
                                                     source_col_map, splitting_col_list)
                t_merge_total += time.time() - t0
            else:
                merged_rows = split_result_rows

            t0 = time.time()
            for result_row in merged_rows:
                # Write values via append (fast bulk insertion)
                result.append([cell.value for cell in result_row])
                # Copy styles for this row
                if keep_style:
                    for cell in result_row:
                        new_cell = result.cell(row=current_row, column=cell.column)
                        copy_cell_style(cell, new_cell)
                current_row += 1
            t_write_total += time.time() - t0

        total_elapsed = time.time() - t_total_start
        print(f"处理耗时分析：拆分 {t_split_total:.1f}s, 合并 {t_merge_total:.1f}s, 写入 {t_write_total:.1f}s, 总计 {total_elapsed:.1f}s")

        # Copy column dimensions
        for col in source.column_dimensions:
            result.column_dimensions[col].width = source.column_dimensions[col].width

        # Copy row dimensions
        for row in source.row_dimensions:
            result.row_dimensions[row].height = source.row_dimensions[row].height

        # Save the output file
        print("处理完成，正在保存输出文件...")
        output_wb.save(output_path)
        print("输出文件保存成功")

        # Verify output after save
        print("正在验证输出结果...")
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