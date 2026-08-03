import unittest
import os
import sys
import yaml
from io import StringIO
from openpyxl import Workbook, load_workbook
from main import process_excel, load_config

class TestExcelSplitter(unittest.TestCase):
    def setUp(self):
        # Create test configuration
        self.config = {
            'merge_by_payment_account': True,
            'input': {
                'path': 'test_input.xlsx',
                'sheet': {
                    'source': {
                        'name': '工资',
                        'columns': {
                            'employee_id': '工号',
                            'project_id': '费用所属中心',
                            'project_category': '费用类别',
                            'project_hours': '实际出勤',
                            'payment_account': '支付账号',
                            'employer_name': '工资所属单位'
                        }
                    },
                    'reference': {
                        'name': '工时',
                        'columns': {
                            'employee_id': '工号',
                            'project_id': '费用所属中心',
                            'project_category': '费用类别',
                            'project_hours': '实际出勤'
                        }
                    },
                    'payment': {
                        'name': '支付规则',
                        'columns': {
                            'project_id': '费用所属中心',
                            'payment_account': '支付账号',
                            'employer_name': '公司'
                        }
                    }
                },
                'splitting_columns': ['基本工资', '岗位工资']
            },
            'output': {
                'path': 'test_output.xlsx',
                'sheet': {
                    'result': {
                        'name': '工资拆分'
                    }
                }
            }
        }

        # Create test input Excel file
        self.wb = Workbook()
        # Remove default sheet
        if 'Sheet' in self.wb.sheetnames:
            self.wb.remove(self.wb['Sheet'])
        # Create our sheets
        self.source_sheet = self.wb.create_sheet('工资')
        self.reference_sheet = self.wb.create_sheet('工时')
        self.payment_sheet = self.wb.create_sheet('支付规则')

    def tearDown(self):
        # Clean up test files
        if os.path.exists('test_input.xlsx'):
            os.remove('test_input.xlsx')
        if os.path.exists('test_output.xlsx'):
            os.remove('test_output.xlsx')

    def test_headers_consistency(self):
        """Test case for ensuring headers consistency between source and result"""
        # Set up source sheet headers according to test case 1
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)

        # Set up reference sheet headers
        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)

        # Set up payment sheet headers
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)

        # Save the workbook
        self.wb.save('test_input.xlsx')

        # Process the Excel file
        process_excel(self.config)

        # Load output file and check headers
        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Result headers should be source headers + payment_account column
        result_headers = [cell.value for cell in result_sheet[1]]
        expected_headers = source_headers + ['支付账号']
        self.assertEqual(expected_headers, result_headers)

    def test_direct_copy(self):
        """Test case for copying rows when no reference match exists"""
        # Set up source sheet according to test case 2
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)

        # Add data row to source
        source_data = ['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A']
        self.source_sheet.append(source_data)

        # Set up reference sheet without matching employee ID
        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        # No data in reference that matches the source

        # Set up payment sheet with mapping for source's project_id
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        # Save the workbook
        self.wb.save('test_input.xlsx')

        # Process the Excel file
        process_excel(self.config)

        # Load output file and check data
        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Check if data in row 2 matches the source data plus payment_account
        result_data = [cell.value for cell in result_sheet[2]]
        expected_data = source_data + ['Account_RD']
        self.assertEqual(expected_data, result_data)

    def test_splitting(self):
        """Test case for splitting rows based on reference data"""
        # Set up source sheet according to test case 3
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)

        # Add data row to source
        source_data = ['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A']
        self.source_sheet.append(source_data)

        # Set up reference sheet with matching employee ID but different project allocations
        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)

        # Add reference data rows
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])
        self.reference_sheet.append(['张三', 'AA', '研发', '2', 4])
        self.reference_sheet.append(['张三', 'AA', '销售', '3', 4])

        # Set up payment sheet: each project maps to a distinct account (no merging)
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account1', '公司A'])
        self.payment_sheet.append(['2', 'Account2', '公司A'])
        self.payment_sheet.append(['3', 'Account3', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        # Save the workbook
        self.wb.save('test_input.xlsx')

        # Process the Excel file
        process_excel(self.config)

        # Load output file and check data
        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Expected results with payment_account column added (no merge since accounts differ)
        expected_results = [
            ['张三', 'AA', '中国', 111.11, 333.33, '研发', '1', 1, 'BB', '公司A', 'Account1'],
            ['张三', 'AA', '中国', 444.44, 1333.33, '研发', '2', 4, 'BB', '公司A', 'Account2'],
            ['张三', 'AA', '中国', 444.44, 1333.33, '销售', '3', 4, 'BB', '公司A', 'Account3']
        ]

        # Check if each row matches the expected split results
        for i, expected in enumerate(expected_results, start=2):
            result_row = [cell.value for cell in result_sheet[i]]

            # Compare each value with a tolerance for floating point values
            for j, (expected_val, actual_val) in enumerate(zip(expected, result_row)):
                if isinstance(expected_val, (int, float)) and isinstance(actual_val, (int, float)):
                    self.assertAlmostEqual(expected_val, actual_val, places=1)
                else:
                    self.assertEqual(expected_val, actual_val)

    # --- New tests for merge by payment account ---

    def test_merge_by_payment_account(self):
        """Merge rows that share the same payment account"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        source_data = ['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A']
        self.source_sheet.append(source_data)

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])
        self.reference_sheet.append(['张三', 'AA', '研发', '2', 4])
        self.reference_sheet.append(['张三', 'AA', '销售', '3', 4])

        # Projects 1 and 2 share Account X, project 3 has Account Y
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['2', 'Account_X', '公司A'])
        self.payment_sheet.append(['3', 'Account_Y', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Expected: 2 rows (projects 1+2 merged, project 3 separate)
        # Row 1: projects "1,2" merged, hours = 1+4 = 5, salaries = 111.11+444.44 = 555.55
        # Row 2: project "3" alone, hours = 4, salaries = 444.44
        expected_results = [
            ['张三', 'AA', '中国', 555.55, 1666.66, '研发', '1,2', 5, 'BB', '公司A', 'Account_X'],
            ['张三', 'AA', '中国', 444.44, 1333.33, '销售', '3', 4, 'BB', '公司A', 'Account_Y']
        ]

        for i, expected in enumerate(expected_results, start=2):
            result_row = [cell.value for cell in result_sheet[i]]
            for j, (expected_val, actual_val) in enumerate(zip(expected, result_row)):
                if isinstance(expected_val, (int, float)) and isinstance(actual_val, (int, float)):
                    self.assertAlmostEqual(expected_val, actual_val, places=1)
                else:
                    self.assertEqual(expected_val, actual_val)

    def test_no_merge_needed(self):
        """Each project maps to distinct account, no merge occurs"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        source_data = ['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A']
        self.source_sheet.append(source_data)

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 5])
        self.reference_sheet.append(['张三', 'AA', '销售', '3', 4])

        # Distinct accounts
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_1', '公司A'])
        self.payment_sheet.append(['3', 'Account_3', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Should have 2 rows (no merging)
        result_rows = list(result_sheet.iter_rows(min_row=2))
        self.assertEqual(len(result_rows), 2)

    def test_merge_with_mixed_categories(self):
        """Merge rows with different project_categories - categories comma-separated"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        source_data = ['李四', 'BB', '中国', 2000.00, 4000.00, '研发', '研发部', 21, 'CC', '公司A']
        self.source_sheet.append(source_data)

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['李四', 'BB', '研发', '1', 2])
        self.reference_sheet.append(['李四', 'BB', '销售', '2', 3])

        # Both projects map to same account, but have different categories
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['2', 'Account_X', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Single merged row: project_id "1,2", categories "研发,销售"
        result_row = [cell.value for cell in result_sheet[2]]
        # project_id = "1,2" (merged), category = "研发,销售"
        self.assertEqual(result_row[5], '研发,销售')   # project_category column
        self.assertEqual(result_row[6], '1,2')          # project_id (merged)
        self.assertEqual(result_row[7], 5)              # total hours
        self.assertEqual(result_row[10], 'Account_X')    # payment_account

    # --- Validation tests ---

    def test_reference_duplicate_employee_project(self):
        """Reference table has duplicate (employee_id, project_id) -> fatal"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        # Duplicate (AA, 1) pairs
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 4])

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_payment_duplicate_project_id(self):
        """Payment table has duplicate project_id -> fatal"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['1', 'Account_Y', '公司A'])  # Duplicate project_id
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_payment_empty_account(self):
        """Payment has non-empty project_id with empty payment_account -> fatal"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', None])  # Empty account
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_source_project_not_in_payment(self):
        """Source project_id missing from payment -> fatal"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        # Source project_id = "研发部" but no payment mapping for it
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        # Only project "1", no "研发部"
        self.payment_sheet.append(['1', 'Account_X', '公司A'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_reference_project_not_in_payment(self):
        """Reference has project_id not in payment -> fatal"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        # Reference has project_id "99" not in payment
        self.reference_sheet.append(['张三', 'AA', '研发', '99', 5])

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_source_project_not_in_payment_but_will_be_split(self):
        """Source project_id not in payment is OK if row will be split (project_id comes from reference)"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        # Source has project_id "研发部" not in payment, but employee has reference match
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])
        self.reference_sheet.append(['张三', 'AA', '研发', '2', 4])

        # Payment has reference project_ids but NOT source's "研发部"
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['2', 'Account_X', '公司A'])

        self.wb.save('test_input.xlsx')
        # Should NOT fatal — source's project_id "研发部" will be replaced by reference's project_ids
        # which are both in payment
        process_excel(self.config)

        # Verify output exists and has merged rows
        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']
        result_row = [cell.value for cell in result_sheet[2]]
        # project_id should be "1,2" (from reference, merged by account), not "研发部"
        self.assertEqual(result_row[6], '1,2')
        self.assertEqual(result_row[10], 'Account_X')


    # --- Merge key correctness ---

    def test_different_employees_same_account_not_merged(self):
        """Different employees sharing same payment account should NOT be merged"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])
        self.source_sheet.append(['李四', 'CC', '中国', 2000.00, 4000.00, '研发', '研发部', 21, 'DD', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 5])
        self.reference_sheet.append(['李四', 'CC', '研发', '1', 10])

        # Both employees' projects map to the SAME account
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Should have 2 rows — one per employee, NOT merged together
        result_rows = list(result_sheet.iter_rows(min_row=2))
        self.assertEqual(len(result_rows), 2,
                         "Different employees should not merge even with same account")

        row1 = [cell.value for cell in result_rows[0]]
        row2 = [cell.value for cell in result_rows[1]]

        # Employee AA: salary 1000/3000 fully to project 1, account Account_X
        self.assertEqual(row1[1], 'AA')
        self.assertEqual(row1[10], 'Account_X')

        # Employee CC: salary 2000/4000 fully to project 1, account Account_X
        self.assertEqual(row2[1], 'CC')
        self.assertEqual(row2[10], 'Account_X')

    # --- Merge scope ---

    def test_same_employee_multiple_source_rows_not_merged(self):
        """Same employee with multiple source rows should NOT merge across source rows"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        # Same employee (AA), two source rows with different salary data
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])
        self.source_sheet.append(['张三', 'AA', '中国', 500.00,  1500.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 10])

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Should have 2 rows — each source row independently split & merged
        result_rows = list(result_sheet.iter_rows(min_row=2))
        self.assertEqual(len(result_rows), 2,
                         "Same employee's multiple source rows should not merge across source rows")

        row1 = [cell.value for cell in result_rows[0]]
        row2 = [cell.value for cell in result_rows[1]]

        # First source row: 基本工资=1000, 岗位工资=3000
        self.assertAlmostEqual(row1[3], 1000.00, places=1)
        self.assertAlmostEqual(row1[4], 3000.00, places=1)

        # Second source row: 基本工资=500, 岗位工资=1500
        self.assertAlmostEqual(row2[3], 500.00, places=1)
        self.assertAlmostEqual(row2[4], 1500.00, places=1)

    # --- Mixed split / non-split ---

    def test_mixed_split_and_no_split_rows(self):
        """One source row splits, another doesn't — both handled correctly"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        # Row 1: has reference match → will be split, source project_id ignored
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', 'no_such_project', 21, 'BB', '公司A'])
        # Row 2: no reference match → copied as-is, source project_id MUST be in payment
        self.source_sheet.append(['李四', 'CC', '中国', 2000.00, 5000.00, '研发', '研发部', 21, 'DD', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 5])
        self.reference_sheet.append(['张三', 'AA', '研发', '2', 5])

        # Payment has reference project_ids AND source row 2's project_id, but NOT row 1's
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['2', 'Account_Y', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])
        # Note: no "no_such_project" in payment, but that's OK because row 1 splits

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        result_rows = list(result_sheet.iter_rows(min_row=2))
        self.assertEqual(len(result_rows), 3,
                         "Row 1 splits into 2 (distinct accounts) + Row 2 copied as 1 = 3 rows")

        # Row 1 split results: project "1" -> Account_X, project "2" -> Account_Y
        row1_data = [cell.value for cell in result_rows[0]]
        row2_data = [cell.value for cell in result_rows[1]]
        self.assertIn(row1_data[6], ['1', '2'])
        self.assertIn(row1_data[10], ['Account_X', 'Account_Y'])

        # Row 2 (no split): should retain project_id "研发部" and get Account_RD
        row3_data = [cell.value for cell in result_rows[2]]
        self.assertEqual(row3_data[1], 'CC')
        self.assertEqual(row3_data[6], '研发部')
        self.assertEqual(row3_data[10], 'Account_RD')

    # --- Config validation tests ---

    def _make_minimal_config(self):
        """Helper: minimal valid config dict."""
        return {
            'input': {
                'path': 'test_input.xlsx',
                'sheet': {
                    'source': {
                        'name': '工资',
                        'columns': {
                            'employee_id': '工号',
                            'project_id': '费用所属中心',
                            'project_category': '费用类别',
                            'project_hours': '实际出勤',
                            'payment_account': '支付账号',
                            'employer_name': '工资所属单位'
                        }
                    },
                    'reference': {
                        'name': '工时',
                        'columns': {
                            'employee_id': '工号',
                            'project_id': '费用所属中心',
                            'project_category': '费用类别',
                            'project_hours': '实际出勤'
                        }
                    },
                    'payment': {
                        'name': '支付规则',
                        'columns': {
                            'project_id': '费用所属中心',
                            'payment_account': '支付账号',
                            'employer_name': '公司'
                        }
                    }
                },
                'splitting_columns': ['基本工资']
            },
            'output': {
                'path': 'test_output.xlsx',
                'sheet': {
                    'result': {
                        'name': '工资拆分'
                    }
                }
            }
        }

    def test_valid_config_passes_check(self):
        """Valid config should pass validate_config without error."""
        from main import validate_config
        config = self._make_minimal_config()
        self.assertFalse(validate_config(config))  # merge_by_payment_account defaults to False

    def test_config_missing_input_section(self):
        """Config missing 'input' key -> SystemExit."""
        from main import validate_config
        with self.assertRaises(SystemExit):
            validate_config({'output': {}})

    def test_config_missing_input_path(self):
        """Config missing input.path -> SystemExit."""
        from main import validate_config
        config = self._make_minimal_config()
        del config['input']['path']
        with self.assertRaises(SystemExit):
            validate_config(config)

    def test_config_missing_splitting_columns(self):
        """Config missing splitting_columns -> SystemExit."""
        from main import validate_config
        config = self._make_minimal_config()
        del config['input']['splitting_columns']
        with self.assertRaises(SystemExit):
            validate_config(config)

    def test_config_non_list_splitting_columns(self):
        """Config with non-list splitting_columns -> SystemExit."""
        from main import validate_config
        config = self._make_minimal_config()
        config['input']['splitting_columns'] = 'not_a_list'
        with self.assertRaises(SystemExit):
            validate_config(config)

    def test_config_missing_output_section(self):
        """Config missing 'output' section -> SystemExit."""
        from main import validate_config
        config = self._make_minimal_config()
        del config['output']
        with self.assertRaises(SystemExit):
            validate_config(config)

    def test_config_missing_source_name(self):
        """Config missing source.name -> SystemExit."""
        from main import validate_config
        config = self._make_minimal_config()
        del config['input']['sheet']['source']['name']
        with self.assertRaises(SystemExit):
            validate_config(config)

    def test_config_missing_reference_columns(self):
        """Config missing reference columns -> SystemExit."""
        from main import validate_config
        config = self._make_minimal_config()
        del config['input']['sheet']['reference']['columns']['project_hours']
        with self.assertRaises(SystemExit):
            validate_config(config)

    # --- Data quality pre-check tests ---

    def test_none_employee_id_in_reference(self):
        """Reference row with None employee_id -> SystemExit."""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', None, '研发', '1', 5])  # None employee_id

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_none_employee_id_in_source(self):
        """Source row with None employee_id -> SystemExit."""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', None, '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 5])

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_negative_hours_in_reference(self):
        """Reference row with negative hours -> SystemExit."""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', -5])  # Negative hours

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_non_numeric_hours_in_reference(self):
        """Reference row with text in hours column -> SystemExit."""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 'N/A'])  # Non-numeric hours

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_employee_id_type_mismatch(self):
        """Mixed int/str employee_id across sheets -> SystemExit."""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        # Reference uses int type for employee_id, source uses str
        self.reference_sheet.append(['张三', 123, '研发', '1', 5])

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    # --- Output verification tests ---

    def test_output_sum_consistency(self):
        """Splitting column totals in output should match source sums."""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])
        self.source_sheet.append(['李四', 'BB', '中国', 2000.00, 4000.00, '研发', '研发部', 21, 'CC', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 2])
        self.reference_sheet.append(['张三', 'AA', '研发', '2', 3])

        # Distinct accounts
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_1', '公司A'])
        self.payment_sheet.append(['2', 'Account_2', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        # Verify output sums
        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        for col_idx in [4, 5]:  # 基本工资 and 岗位工资
            result_sum = sum(
                float(row[col_idx - 1].value)
                for row in result_sheet.iter_rows(min_row=2)
                if row[col_idx - 1].value is not None
            )
            source_sum = sum(
                float(row[col_idx - 1].value)
                for row in self.source_sheet.iter_rows(min_row=2)
                if row[col_idx - 1].value is not None
            )
            self.assertAlmostEqual(result_sum, source_sum, places=1)

    def test_output_file_valid(self):
        """Output file can be reopened and has expected structure."""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '1', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 5])

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        # Verify output file
        self.assertTrue(os.path.exists('test_output.xlsx'))
        wb = load_workbook('test_output.xlsx')
        self.assertIn('工资拆分', wb.sheetnames)
        self.assertIn('工资', wb.sheetnames)
        self.assertIn('工时', wb.sheetnames)
        wb.close()

    # --- merge_by_payment_account integration test ---

    def test_split_without_merge(self):
        """merge_by_payment_account=False (default): splits correctly, payment_account populated, no merge."""
        config = {
            'merge_by_payment_account': False,
            'input': {
                'path': 'test_input.xlsx',
                'sheet': {
                    'source': {
                        'name': '工资',
                        'columns': {
                            'employee_id': '工号',
                            'project_id': '费用所属中心',
                            'project_category': '费用类别',
                            'project_hours': '实际出勤',
                            'payment_account': '支付账号',
                            'employer_name': '工资所属单位'
                        }
                    },
                    'reference': {
                        'name': '工时',
                        'columns': {
                            'employee_id': '工号',
                            'project_id': '费用所属中心',
                            'project_category': '费用类别',
                            'project_hours': '实际出勤'
                        }
                    },
                    'payment': {
                        'name': '支付规则',
                        'columns': {
                            'project_id': '费用所属中心',
                            'payment_account': '支付账号',
                            'employer_name': '公司'
                        }
                    }
                },
                'splitting_columns': ['基本工资', '岗位工资']
            },
            'output': {
                'path': 'test_output.xlsx',
                'sheet': {
                    'result': {
                        'name': '工资拆分'
                    }
                }
            }
        }

        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 2])
        self.reference_sheet.append(['张三', 'AA', '研发', '2', 3])

        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_1', '公司A'])
        self.payment_sheet.append(['2', 'Account_2', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        process_excel(config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Should have 2 rows (split but not merged)
        result_rows = list(result_sheet.iter_rows(min_row=2))
        self.assertEqual(len(result_rows), 2)

        # Headers should include payment_account
        result_headers = [cell.value for cell in result_sheet[1]]
        expected_headers = source_headers + ['支付账号']
        self.assertEqual(result_headers, expected_headers)

        # Verify split values and payment_account populated
        row1 = [cell.value for cell in result_rows[0]]
        row2 = [cell.value for cell in result_rows[1]]
        # Total 基本工资 = 1000, split 2/5 and 3/5
        self.assertAlmostEqual(row1[3], 400.00, places=1)
        self.assertAlmostEqual(row2[3], 600.00, places=1)
        # Total 岗位工资 = 3000, split 2/5 and 3/5
        self.assertAlmostEqual(row1[4], 1200.00, places=1)
        self.assertAlmostEqual(row2[4], 1800.00, places=1)
        # Each row has its own payment_account
        self.assertEqual(row1[10], 'Account_1')
        self.assertEqual(row2[10], 'Account_2')

    # --- Composite key (employer_name, project_id) tests ---

    def test_composite_key_same_project_diff_employer_ok(self):
        """Same project_id with different employer_name is NOT a duplicate — both valid."""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 10])

        # Same project_id "1" with two different employers — both valid
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['1', 'Account_Y', '公司B'])
        self.payment_sheet.append(['研发部', 'Account_X', '公司A'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']
        result_row = [cell.value for cell in result_sheet[2]]
        # AA/公司A + project "1" → Account_X
        self.assertEqual(result_row[10], 'Account_X')

    def test_composite_key_different_employer_diff_account(self):
        """Same project_id + different employer_name → different accounts, not merged."""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        # Same employee "AA", two source rows with different employers
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])
        self.source_sheet.append(['张三', 'AA', '中国', 500.00,  1500.00, '研发', '研发部', 21, 'BB', '公司B'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 10])

        # Same project_id "1", different employers → different accounts
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['1', 'Account_Y', '公司B'])
        self.payment_sheet.append(['研发部', 'Account_X', '公司A'])
        self.payment_sheet.append(['研发部', 'Account_Y', '公司B'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']
        result_rows = list(result_sheet.iter_rows(min_row=2))

        # Two rows (different source rows → not merged), different accounts
        self.assertEqual(len(result_rows), 2)
        row1 = [cell.value for cell in result_rows[0]]
        row2 = [cell.value for cell in result_rows[1]]
        self.assertEqual(row1[10], 'Account_X')
        self.assertEqual(row2[10], 'Account_Y')
        self.assertAlmostEqual(row1[3], 1000.00, places=1)
        self.assertAlmostEqual(row2[3], 500.00, places=1)

    def test_composite_key_missing_pair_in_payment(self):
        """Split row's (employer_name, project_id) not in payment → fatal."""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        # Reference project_id "99" not in payment for 公司A
        self.reference_sheet.append(['张三', 'AA', '研发', '99', 10])

        # Payment has project "99" but only for 公司B — not 公司A
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['99', 'Account_Z', '公司B'])
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_composite_key_none_employer_in_payment(self):
        """Payment row with empty employer_name is skipped."""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导', '工资所属单位']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB', '公司A'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 10])

        # Payment has a row with empty employer_name (should be skipped)
        # and another row with valid employer_name for the same project_id
        payment_headers = ['费用所属中心', '支付账号', '公司']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X', '公司A'])
        self.payment_sheet.append(['1', 'Account_IGNORED', None])  # Empty employer → skipped
        self.payment_sheet.append(['研发部', 'Account_RD', '公司A'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']
        result_row = [cell.value for cell in result_sheet[2]]
        # Should match (公司A, 1) → Account_X, ignore the None-employer row
        self.assertEqual(result_row[10], 'Account_X')


if __name__ == '__main__':
    unittest.main()
