# requirement

## 配置文件

```yaml config.yaml
input:
  path: "项目成本.xlsx"  
  sheet:
    source:
      name: "工资"
      columns:
        employee_id: "工号"
        project_id: "费用所属中心"
        project_category: "费用类别"
        project_hours: "实际出勤"
    reference:
      name: "工时"
      columns:
        employee_id: "工号"
        project_id: "费用所属中心"
        project_category: "费用类别"
        project_hours: "实际出勤"
  splitting_columns:
  - 基本工资
  - 岗位工资
output:
  path: "项目成本拆分.xlsx"
  sheet:
    result:
      name: "工资拆分"
```

## 编程规范

- 编写语言为python，要求按python编程规范编写程序
- 默认从配置文件中读取配置，配置文件路径可通过命令行参数设置。可从命令行参数中读取输入文件名和表名、输出文件名和表名
- 检查输入文件，如果无法拆分直接退出，并输出无法拆分的原因
- 编写测试用例，确保拆分逻辑正确
- 文件编码方式采用统一采用UTF8

## 数据描述

- 配置文件input.splitting_columns下的键值对表示需要拆分的列，键值对中键为列的标识，值为列的名称
- 配置文件input.sheet..columns下的键值对表示处理过程中涉及到的列，键值对中键为列的标识，值为列的名称，查找列的标识对应的列时需要通过在表中查找列的名称实现

## 数据校验

- 表source中列employee_id必须存在，列project_hours存在与否均可，不过需要确保表result和表source的表头完全一致
- 表source中需要拆分的列必须存在
- 表reference中列employee_id project_id project_category project_hours必须存在

## 拆分规则

- 以表source为基础，参考表reference进行拆分，拆分结果保存到表result中
- 表result与表source列的名称和顺序完全相同
- 表source中列employee_id和表reference中列employee_id是左连接关系，通过列的名称定位列
  - 如果通过employee_id在表reference中找到了对应的记录
    - 列project_id project_category project_hours内容按列名从表reference中获取
    - 配置文件input.splitting_columns中定义的行以表reference中列project-hours为准按比例进行拆分
    - 未在配置文件input.splitting_columns和input.sheet.source.columns中定义的列以表source为准保持不变
    - 表result中拆分后的行的数字格式同表source中拆分前的行
  - 如果通过employee_id在表reference中未找到对应的记录
    - 表source中该行整体复制到表result，包括该行的数字格式

## 底层实现

- 通过pandas包实现数据拆分
- 通过openpyxl包实现格式设置

## 异常处理

- 直接复制单元格样式对象会导致openpyxl内部样式索引不一致，通过显式复制各个样式属性而不是直接操作内部_style对象，可以避免openpyxl内部样式索引不一致的问题
- 在使用read_only=True模式加载Excel文件时提示：AttributeError: 'ReadOnlyWorksheet' object has no attribute 'columns'，改用read_only=False模式
- 针对生成的 result 表头与 source 表不一致的问题，根本原因在于数据处理时列名被转换为内部标识符，但输出时未还原为原始列名

## 现有代码

```python main.py
import openpyxl
from openpyxl.styles import Font, Border, Side, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.cell import Cell
import yaml
import argparse
import sys
from collections import defaultdict


def copy_style(source_cell, target_cell):
    """复制源单元格的样式到目标单元格"""
    if source_cell.font:
        target_cell.font = Font(
            name=source_cell.font.name,
            size=source_cell.font.size,
            bold=source_cell.font.bold,
            italic=source_cell.font.italic,
            underline=source_cell.font.underline,
            strike=source_cell.font.strike,
            color=source_cell.font.color
        )
    if source_cell.border:
        target_cell.border = Border(
            left=Side(style=source_cell.border.left.style, color=source_cell.border.left.color),
            right=Side(style=source_cell.border.right.style, color=source_cell.border.right.color),
            top=Side(style=source_cell.border.top.style, color=source_cell.border.top.color),
            bottom=Side(style=source_cell.border.bottom.style, color=source_cell.border.bottom.color)
        )
    if source_cell.fill:
        target_cell.fill = PatternFill(
            start_color=source_cell.fill.start_color,
            end_color=source_cell.fill.end_color,
            fill_type=source_cell.fill.fill_type
        )
    if source_cell.alignment:
        target_cell.alignment = Alignment(
            horizontal=source_cell.alignment.horizontal,
            vertical=source_cell.alignment.vertical,
            wrap_text=source_cell.alignment.wrap_text,
            shrink_to_fit=source_cell.alignment.shrink_to_fit,
            indent=source_cell.alignment.indent
        )
    target_cell.number_format = source_cell.number_format


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Excel数据拆分工具')
    parser.add_argument('--config', default='config.yaml', help='配置文件路径')
    parser.add_argument('--input', help='输入文件路径')
    parser.add_argument('--output', help='输出文件路径')
    args = parser.parse_args()

    # 加载配置文件
    with open(args.config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    if args.input:
        config['input']['path'] = args.input
    if args.output:
        config['output']['path'] = args.output

    # 加载工作簿
    try:
        wb = openpyxl.load_workbook(config['input']['path'], read_only=False)
    except FileNotFoundError:
        print(f"错误：输入文件 {config['input']['path']} 不存在")
        sys.exit(1)

    # 获取工作表配置
    source_sheet_name = config['input']['sheet']['source']['name']
    reference_sheet_name = config['input']['sheet']['reference']['name']
    if source_sheet_name not in wb.sheetnames:
        print(f"错误：源工作表 {source_sheet_name} 不存在")
        sys.exit(1)
    if reference_sheet_name not in wb.sheetnames:
        print(f"错误：参考工作表 {reference_sheet_name} 不存在")
        sys.exit(1)
    source_sheet = wb[source_sheet_name]
    reference_sheet = wb[reference_sheet_name]

    # 解析列配置
    def get_column_indices(sheet, columns_config):
        header = [cell.value for cell in sheet[1]]  # 获取表头值列表
        indices = {}
        for key, col_name in columns_config.items():
            if col_name not in header:
                print(f"错误：列 {col_name} 不存在于工作表 {sheet.title}")
                sys.exit(1)
            indices[key] = header.index(col_name) + 1  # 转为1-based
        return indices

    source_cols = get_column_indices(source_sheet, config['input']['sheet']['source']['columns'])
    ref_cols = get_column_indices(reference_sheet, config['input']['sheet']['reference']['columns'])

    # 获取源表头并验证拆分列
    source_header = [cell.value for cell in source_sheet[1]]
    splitting_columns = config['input']['splitting_columns']
    for col_name in splitting_columns:
        if col_name not in source_header:
            print(f"错误：拆分列 '{col_name}' 不存在于源工作表 {source_sheet.title}")
            sys.exit(1)
    splitting_col_indices = [source_header.index(col_name) + 1 for col_name in splitting_columns]

    # 验证参考表工时列
    for row in reference_sheet.iter_rows(min_row=2):
        hours_cell = row[ref_cols['project_hours'] - 1]
        if hours_cell.value is None or hours_cell.value <= 0:
            print(f"错误：参考工作表 {reference_sheet_name} 中存在无效工时值（行 {row[0].row}）")
            sys.exit(1)

    # 预处理参考数据
    ref_data = defaultdict(list)
    for row in reference_sheet.iter_rows(min_row=2):
        emp_id = row[ref_cols['employee_id'] - 1].value
        ref_data[emp_id].append({
            'project_id': row[ref_cols['project_id'] - 1].value,
            'project_category': row[ref_cols['project_category'] - 1].value,
            'project_hours': row[ref_cols['project_hours'] - 1].value
        })

    # 准备输出工作簿
    output_wb = openpyxl.Workbook()
    output_sheet = output_wb.active
    output_sheet.title = config['output']['sheet']['result']['name']

    # 复制列宽
    for col in source_sheet.columns:
        col_letter = get_column_letter(col[0].column)
        output_sheet.column_dimensions[col_letter].width = source_sheet.column_dimensions[col_letter].width

    # 复制表头
    header_row = [cell.value for cell in source_sheet[1]]
    output_sheet.append(header_row)
    # 复制表头样式
    for col_idx, cell in enumerate(source_sheet[1], start=1):
        copy_style(cell, output_sheet.cell(row=1, column=col_idx))

    # 处理数据行
    for src_row in source_sheet.iter_rows(min_row=2):
        emp_id = src_row[source_cols['employee_id'] - 1].value
        refs = ref_data.get(emp_id, [])

        if not refs:
            # 直接复制行
            new_row = []
            for cell in src_row:
                new_cell = Cell(output_sheet, value=cell.value)
                copy_style(cell, new_cell)
                new_row.append(new_cell)
            output_sheet.append(new_row)
            # 复制行高
            output_sheet.row_dimensions[output_sheet.max_row].height = source_sheet.row_dimensions[
                src_row[0].row].height
        else:
            total_hours = sum(r['project_hours'] for r in refs)
            for ref in refs:
                new_row_num = output_sheet.max_row + 1
                for col_idx, src_cell in enumerate(src_row, start=1):
                    target_cell = output_sheet.cell(row=new_row_num, column=col_idx)

                    # 处理特殊列
                    if col_idx == source_cols['project_id']:
                        value = ref['project_id']
                    elif col_idx == source_cols['project_category']:
                        value = ref['project_category']
                    elif col_idx == source_cols['project_hours']:
                        value = ref['project_hours']
                    elif src_cell.value is None:
                        value = None
                    elif col_idx in splitting_col_indices:
                        ratio = ref['project_hours'] / total_hours
                        value = src_cell.value * ratio
                    else:
                        value = src_cell.value

                    target_cell.value = value
                    copy_style(src_cell, target_cell)

                # 复制行高
                output_sheet.row_dimensions[new_row_num].height = source_sheet.row_dimensions[src_row[0].row].height

    # 保存输出
    output_wb.save(config['output']['path'])


if __name__ == '__main__':
    main()
```
