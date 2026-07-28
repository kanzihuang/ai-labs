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
                            'project_account': '支付账号'
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
                            'project_account': '支付账号'
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
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)

        # Set up reference sheet headers
        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)

        # Set up payment sheet headers
        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)

        # Save the workbook
        self.wb.save('test_input.xlsx')

        # Process the Excel file
        process_excel(self.config)

        # Load output file and check headers
        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Result headers should be source headers + project_account column
        result_headers = [cell.value for cell in result_sheet[1]]
        expected_headers = source_headers + ['支付账号']
        self.assertEqual(expected_headers, result_headers)

    def test_direct_copy(self):
        """Test case for copying rows when no reference match exists"""
        # Set up source sheet according to test case 2
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)

        # Add data row to source
        source_data = ['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB']
        self.source_sheet.append(source_data)

        # Set up reference sheet without matching employee ID
        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        # No data in reference that matches the source

        # Set up payment sheet with mapping for source's project_id
        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['研发部', 'Account_RD'])

        # Save the workbook
        self.wb.save('test_input.xlsx')

        # Process the Excel file
        process_excel(self.config)

        # Load output file and check data
        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Check if data in row 2 matches the source data plus project_account
        result_data = [cell.value for cell in result_sheet[2]]
        expected_data = source_data + ['Account_RD']
        self.assertEqual(expected_data, result_data)

    def test_splitting(self):
        """Test case for splitting rows based on reference data"""
        # Set up source sheet according to test case 3
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)

        # Add data row to source
        source_data = ['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB']
        self.source_sheet.append(source_data)

        # Set up reference sheet with matching employee ID but different project allocations
        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)

        # Add reference data rows
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])
        self.reference_sheet.append(['张三', 'AA', '研发', '2', 4])
        self.reference_sheet.append(['张三', 'AA', '销售', '3', 4])

        # Set up payment sheet: each project maps to a distinct account (no merging)
        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account1'])
        self.payment_sheet.append(['2', 'Account2'])
        self.payment_sheet.append(['3', 'Account3'])
        self.payment_sheet.append(['研发部', 'Account_RD'])

        # Save the workbook
        self.wb.save('test_input.xlsx')

        # Process the Excel file
        process_excel(self.config)

        # Load output file and check data
        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Expected results with project_account column added (no merge since accounts differ)
        expected_results = [
            ['张三', 'AA', '中国', 111.11, 333.33, '研发', '1', 1, 'BB', 'Account1'],
            ['张三', 'AA', '中国', 444.44, 1333.33, '研发', '2', 4, 'BB', 'Account2'],
            ['张三', 'AA', '中国', 444.44, 1333.33, '销售', '3', 4, 'BB', 'Account3']
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
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)
        source_data = ['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB']
        self.source_sheet.append(source_data)

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])
        self.reference_sheet.append(['张三', 'AA', '研发', '2', 4])
        self.reference_sheet.append(['张三', 'AA', '销售', '3', 4])

        # Projects 1 and 2 share Account X, project 3 has Account Y
        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X'])
        self.payment_sheet.append(['2', 'Account_X'])
        self.payment_sheet.append(['3', 'Account_Y'])
        self.payment_sheet.append(['研发部', 'Account_RD'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Expected: 2 rows (projects 1+2 merged, project 3 separate)
        # Row 1: projects "1,2" merged, hours = 1+4 = 5, salaries = 111.11+444.44 = 555.55
        # Row 2: project "3" alone, hours = 4, salaries = 444.44
        expected_results = [
            ['张三', 'AA', '中国', 555.55, 1666.66, '研发', '1,2', 5, 'BB', 'Account_X'],
            ['张三', 'AA', '中国', 444.44, 1333.33, '销售', '3', 4, 'BB', 'Account_Y']
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
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)
        source_data = ['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB']
        self.source_sheet.append(source_data)

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 5])
        self.reference_sheet.append(['张三', 'AA', '销售', '3', 4])

        # Distinct accounts
        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_1'])
        self.payment_sheet.append(['3', 'Account_3'])
        self.payment_sheet.append(['研发部', 'Account_RD'])

        self.wb.save('test_input.xlsx')
        process_excel(self.config)

        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']

        # Should have 2 rows (no merging)
        result_rows = list(result_sheet.iter_rows(min_row=2))
        self.assertEqual(len(result_rows), 2)

    def test_merge_with_mixed_categories(self):
        """Merge rows with different project_categories - categories comma-separated"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)
        source_data = ['李四', 'BB', '中国', 2000.00, 4000.00, '研发', '研发部', 21, 'CC']
        self.source_sheet.append(source_data)

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['李四', 'BB', '研发', '1', 2])
        self.reference_sheet.append(['李四', 'BB', '销售', '2', 3])

        # Both projects map to same account, but have different categories
        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X'])
        self.payment_sheet.append(['2', 'Account_X'])
        self.payment_sheet.append(['研发部', 'Account_RD'])

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
        self.assertEqual(result_row[9], 'Account_X')    # project_account

    # --- Validation tests ---

    def test_reference_duplicate_employee_project(self):
        """Reference table has duplicate (employee_id, project_id) -> fatal"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        # Duplicate (AA, 1) pairs
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 4])

        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X'])
        self.payment_sheet.append(['研发部', 'Account_RD'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_payment_duplicate_project_id(self):
        """Payment table has duplicate project_id -> fatal"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])

        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X'])
        self.payment_sheet.append(['1', 'Account_Y'])  # Duplicate project_id
        self.payment_sheet.append(['研发部', 'Account_RD'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_payment_empty_account(self):
        """Payment has non-empty project_id with empty project_account -> fatal"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])

        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', None])  # Empty account
        self.payment_sheet.append(['研发部', 'Account_RD'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_source_project_not_in_payment(self):
        """Source project_id missing from payment -> fatal"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)
        # Source project_id = "研发部" but no payment mapping for it
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)

        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)
        # Only project "1", no "研发部"
        self.payment_sheet.append(['1', 'Account_X'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_reference_project_not_in_payment(self):
        """Reference has project_id not in payment -> fatal"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        # Reference has project_id "99" not in payment
        self.reference_sheet.append(['张三', 'AA', '研发', '99', 5])

        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X'])
        self.payment_sheet.append(['研发部', 'Account_RD'])

        self.wb.save('test_input.xlsx')
        with self.assertRaises(SystemExit):
            process_excel(self.config)

    def test_source_project_not_in_payment_but_will_be_split(self):
        """Source project_id not in payment is OK if row will be split (project_id comes from reference)"""
        source_headers = ['姓名', '工号', '部门', '基本工资', '岗位工资', '费用类别', '费用所属中心', '实际出勤', '分管领导']
        self.source_sheet.append(source_headers)
        # Source has project_id "研发部" not in payment, but employee has reference match
        self.source_sheet.append(['张三', 'AA', '中国', 1000.00, 3000.00, '研发', '研发部', 21, 'BB'])

        reference_headers = ['姓名', '工号', '费用类别', '费用所属中心', '实际出勤']
        self.reference_sheet.append(reference_headers)
        self.reference_sheet.append(['张三', 'AA', '研发', '1', 1])
        self.reference_sheet.append(['张三', 'AA', '研发', '2', 4])

        # Payment has reference project_ids but NOT source's "研发部"
        payment_headers = ['费用所属中心', '支付账号']
        self.payment_sheet.append(payment_headers)
        self.payment_sheet.append(['1', 'Account_X'])
        self.payment_sheet.append(['2', 'Account_X'])

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
        self.assertEqual(result_row[9], 'Account_X')


if __name__ == '__main__':
    unittest.main()
