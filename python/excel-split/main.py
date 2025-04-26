import pandas as pd
import yaml
import argparse
import os
import sys
from pandas import ExcelWriter


def load_config(config_path='config.yaml'):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def main():
    # 加载配置文件
    try:
        config = load_config()
    except FileNotFoundError:
        print("错误：配置文件config.yaml未找到。")
        sys.exit(1)
    except Exception as e:
        print(f"读取配置文件时发生错误：{e}")
        sys.exit(1)

    # 解析命令行参数
    parser = argparse.ArgumentParser()
    parser.add_argument('--input_path', help='输入文件路径')
    parser.add_argument('--source_sheet', help='source表的sheet名')
    parser.add_argument('--reference_sheet', help='reference表的sheet名')
    parser.add_argument('--output_path', help='输出文件路径')
    parser.add_argument('--result_sheet', help='结果表的sheet名')
    args = parser.parse_args()

    # 覆盖配置
    if args.input_path:
        config['input']['path'] = args.input_path
    if args.source_sheet:
        config['input']['sheet']['source']['name'] = args.source_sheet
    if args.reference_sheet:
        config['input']['sheet']['reference']['name'] = args.reference_sheet
    if args.output_path:
        config['output']['path'] = args.output_path
    if args.result_sheet:
        config['output']['sheet']['result']['name'] = args.result_sheet

    # 输入输出路径
    input_path = config['input']['path']
    output_path = config['output']['path']
    source_sheet_name = config['input']['sheet']['source']['name']
    reference_sheet_name = config['input']['sheet']['reference']['name']
    splitting_columns = config['input']['splitting_columns']

    # 检查输入文件是否存在
    if not os.path.exists(input_path):
        print(f"错误：输入文件 {input_path} 不存在。")
        sys.exit(1)

    # 读取source表
    try:
        source_df = pd.read_excel(input_path, sheet_name=source_sheet_name)
        source_columns = config['input']['sheet']['source']['columns']
        source_df.rename(columns={v: k for k, v in source_columns.items()}, inplace=True)
    except Exception as e:
        print(f"读取source表失败: {e}")
        sys.exit(1)

    # 读取reference表
    try:
        reference_df = pd.read_excel(input_path, sheet_name=reference_sheet_name)
        reference_columns = config['input']['sheet']['reference']['columns']
        reference_df.rename(columns={v: k for k, v in reference_columns.items()}, inplace=True)
    except Exception as e:
        print(f"读取reference表失败: {e}")
        sys.exit(1)

    # 检查reference表是否存在零值
    if 'project_hours' not in reference_df.columns:
        print("错误：reference表缺少project_hours列")
        sys.exit(1)
    if (reference_df['project_hours'] == 0).any():
        print("错误：reference表中存在project_hours为零的记录")
        sys.exit(1)

    # 检查拆分列是否存在
    for col in splitting_columns:
        if col not in source_df.columns:
            print(f"错误：拆分列 {col} 不存在于source表")
            sys.exit(1)

    # 分组处理
    reference_group = reference_df.groupby('employee_id')
    result_rows = []

    # 处理每一行
    for idx, source_row in source_df.iterrows():
        emp_id = source_row['employee_id']

        if emp_id in reference_group.groups:
            ref_records = reference_group.get_group(emp_id)
            total_hours = ref_records['project_hours'].sum()

            for _, ref_row in ref_records.iterrows():
                ratio = ref_row['project_hours'] / total_hours
                new_row = source_row.copy()

                # 更新项目信息
                new_row['project_id'] = ref_row['project_id']
                new_row['project_category'] = ref_row['project_category']
                new_row['project_hours'] = ref_row['project_hours']

                # 拆分金额
                for col in splitting_columns:
                    new_row[col] = source_row[col] * ratio

                result_rows.append(new_row)
        else:
            result_rows.append(source_row)

    # 创建结果DataFrame
    result_df = pd.DataFrame(result_rows)
    result_df = result_df[source_df.columns]  # 保持列顺序

    # 还原列名为原始中文
    column_mapping = {k: v for k, v in source_columns.items()}
    result_df.rename(columns=column_mapping, inplace=True)

    # 写入输出文件
    try:
        with ExcelWriter(output_path, engine='openpyxl') as writer:
            result_df.to_excel(
                writer,
                sheet_name=config['output']['sheet']['result']['name'],
                index=False
            )
    except Exception as e:
        print(f"写入输出文件失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()