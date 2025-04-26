def test_case1(self):
    # 构造source和reference数据
    source_data = {
        '工号': ['001'],
        '费用所属中心': ['中心A'],
        '费用类别': ['类别X'],
        '实际出勤': [20],
        '基本工资': [1000],
        '岗位工资': [2000]
    }
    source_df = pd.DataFrame(source_data)
    reference_data = {
        '工号': ['001', '001'],
        '费用所属中心': ['中心B', '中心C'],
        '费用类别': ['类别Y', '类别Z'],
        '实际出勤': [10, 30]
    }
    reference_df = pd.DataFrame(reference_data)
    # 保存到Excel文件
    input_path = os.path.join(self.test_dir, 'test_input.xlsx')
    with pd.ExcelWriter(input_path, engine='openpyxl') as writer:
        source_df.to_excel(writer, sheet_name='工资', index=False)
        reference_df.to_excel(writer, sheet_name='工时', index=False)
    # 运行处理函数
    process_data(input_path, '工资', '工时', 'test_output.xlsx', '工资拆分', ['基本工资', '岗位工资'])
    # 读取结果并验证
    result_df = pd.read_excel('test_output.xlsx', sheet_name='工资拆分')
    self.assertEqual(len(result_df), 2)
    # 检查第一行的数据
    row1 = result_df.iloc[0]
    self.assertEqual(row1['工号'], '001')
    self.assertEqual(row1['费用所属中心'], '中心B')
    self.assertEqual(row1['基本工资'], 250)
    self.assertEqual(row1['岗位工资'], 500)
    # 检查第二行
    row2 = result_df.iloc[1]
    self.assertEqual(row2['费用所属中心'], '中心C')
    self.assertEqual(row2['基本工资'], 750)
    self.assertEqual(row2['岗位工资'], 1500)

# 其他测试用例类似