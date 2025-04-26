import pandas as pd

def check_columns(file_path):
    """检查文件实际列名"""
    print("工资表实际列名:", pd.read_excel(file_path, sheet_name="工资", nrows=0).columns.tolist())
    print("工时表实际列名:", pd.read_excel(file_path, sheet_name="工时", nrows=0).columns.tolist())

if __name__ == "__main__":
    check_columns("项目成本.xlsx")