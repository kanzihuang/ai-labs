import pytest
import pandas as pd
import os


def test_full_process(tmp_path):
    # Create test data
    test_data = {
        'source': pd.DataFrame({
            '工号': [1, 2, 3],
            '费用所属中心': ['A', 'B', 'C'],
            '费用类别': ['X', 'Y', 'Z'],
            '实际出勤': [10, 20, 30],
            '基本工资': [1000, 2000, 3000],
            '岗位工资': [500, 600, 700]
        }),
        'reference': pd.DataFrame({
            '工号': [1, 1, 2],
            '费用所属中心': ['A1', 'A2', 'B1'],
            '费用类别': ['X1', 'X2', 'Y1'],
            '实际出勤': [4, 6, 20]
        })
    }

    # Save test files
    input_path = tmp_path / "test_input.xlsx"
    with pd.ExcelWriter(input_path) as writer:
        test_data['source'].to_excel(writer, sheet_name='工资', index=False)
        test_data['reference'].to_excel(writer, sheet_name='工时', index=False)

    # Run program
    config = {
        'input': {
            'path': str(input_path),
            'sheet': {
                'source': {'name': '工资', 'columns': {
                    'employee_id': '工号',
                    'project_id': '费用所属中心',
                    'project_category': '费用类别',
                    'project_hours': '实际出勤'}},
                'reference': {'name': '工时', 'columns': {
                    'employee_id': '工号',
                    'project_id': '费用所属中心',
                    'project_category': '费用类别',
                    'project_hours': '实际出勤'}}
            },
            'splitting_columns': ['基本工资', '岗位工资']
        },
        'output': {
            'path': str(tmp_path / "output.xlsx"),
            'sheet': {'result': {'name': '工资拆分'}}
        }
    }

    # Save config
    config_path = tmp_path / "test_config.yaml"
    with open(config_path, 'w') as f:
        yaml.dump(config, f)

    # Execute
    os.system(f"python split_cost.py --config {config_path}")

    # Verify results
    result = pd.read_excel(config['output']['path'], sheet_name='工资拆分')

    # Validate splitting logic
    expected = pd.DataFrame({
        'employee_id': [1, 1, 2, 3],
        'project_id': ['A1', 'A2', 'B1', 'C'],
        'project_category': ['X1', 'X2', 'Y1', 'Z'],
        'project_hours': [4, 6, 20, 30],
        '基本工资': [400.0, 600.0, 2000.0, 3000.0],
        '岗位工资': [200.0, 300.0, 600.0, 700.0]
    })

    pd.testing.assert_frame_equal(result, expected)