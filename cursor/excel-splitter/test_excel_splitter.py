import unittest
import os
import yaml
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
                            'project_hours': '实际出勤'
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
        
        # Save the workbook
        self.wb.save('test_input.xlsx')
        
        # Process the Excel file
        process_excel(self.config)
        
        # Load output file and check headers
        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']
        
        # Check if headers in result match headers in source
        result_headers = [cell.value for cell in result_sheet[1]]
        self.assertEqual(source_headers, result_headers)

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
        
        # Save the workbook
        self.wb.save('test_input.xlsx')
        
        # Process the Excel file
        process_excel(self.config)
        
        # Load output file and check data
        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']
        
        # Check if data in row 2 matches the source data (direct copy)
        result_data = [cell.value for cell in result_sheet[2]]
        self.assertEqual(source_data, result_data)

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
        
        # Save the workbook
        self.wb.save('test_input.xlsx')
        
        # Process the Excel file
        process_excel(self.config)
        
        # Load output file and check data
        output_wb = load_workbook('test_output.xlsx')
        result_sheet = output_wb['工资拆分']
        
        # 期望结果应与规范一致:
        # 1. 基本工资和岗位工资会按照实际出勤比例拆分
        # 2. 费用类别，费用所属中心，实际出勤从reference表获取
        # 3. 其他列(姓名,工号,部门,分管领导)保持不变
        expected_results = [
            ['张三', 'AA', '中国', 111.11, 333.33, '研发', '1', 1, 'BB'],
            ['张三', 'AA', '中国', 444.44, 1333.33, '研发', '2', 4, 'BB'],
            ['张三', 'AA', '中国', 444.44, 1333.33, '销售', '3', 4, 'BB']
        ]
        
        # Check if each row matches the expected split results
        for i, expected in enumerate(expected_results, start=2):
            result_row = [cell.value for cell in result_sheet[i]]
            
            # Compare each value with a tolerance for floating point values
            for j, (expected_val, actual_val) in enumerate(zip(expected, result_row)):
                if isinstance(expected_val, (int, float)) and isinstance(actual_val, (int, float)):
                    self.assertAlmostEqual(expected_val, actual_val, places=2)
                else:
                    self.assertEqual(expected_val, actual_val)

if __name__ == '__main__':
    unittest.main() 