# 需求

## 配置文件

```yaml config.yaml
input:
  path: "input/项目成本.xlsx"  
  sheet:
    source:
      name: "工资"
      columns:
        employee_id: "工号"
        project_id: "费用所属中心"
        project_category: "费用类别"
        project_hours: "实际出勤"
        project_account: "支付账号"
    reference:
      name: "工时"
      columns:
        employee_id: "工号"
        project_id: "费用所属中心"
        project_category: "费用类别"
        project_hours: "实际出勤"
    payment:
      name: "支付规则"  # 可选，不配置则不合并
      columns:
        project_id: "费用所属中心"
        project_account: "支付账号"
  splitting_columns:
  - 基本工资
  - 岗位工资
output:
  path: "output/项目成本拆分.xlsx"
  sheet:
    result:
      name: "工资拆分"
```

> 支付规则表(payment)是可选的。如果不配置 payment 表，则不进行支付账号合并，结果表中也不添加支付账号列。

## 配置验证

在处理开始之前，调用 `validate_config()` 验证配置文件结构。校验内容包括：

- `input.path` 是否存在且为有效字符串
- `input.sheet.source` 及 `source.columns.employee_id` 是否存在
- `input.sheet.reference` 及 `reference.columns` 下四个必填字段是否存在
- `input.splitting_columns` 是否为非空列表，检测其中的重复条目
- payment（可选）：如果配置了 payment，需要有效的 `name`、`columns.project_id` 和 `columns.project_account`
- 冲突检测：如果 `source.columns` 中包含 `project_account` 但未正确配置 payment 表，则报错
- `output.path`、`output.sheet.result.name` 是否存在且有效

所有配置错误一次性收集并输出。

## 编程规范

- 编写语言为python，要求按python编程规范编写程序
- 默认从配置文件中读取配置，配置文件路径可通过命令行参数设定
- 首先调用 `validate_config()` 验证配置文件结构，如果配置有误直接退出并输出详细原因
- 检查输入文件，如果无法拆分直接退出，并输出无法拆分的原因
- 所有数据验证错误一次性收集并输出，便于一次性修正
- 处理完成后调用 `verify_output()` 验证输出文件的完整性
- 文件编码方式统一采用UTF8

## 数据描述

- 配置文件input.splitting_columns下的键值对表示需要拆分的列
- 配置文件input.sheet.*.columns下的键值对表示处理过程中涉及到的列，键为列的标识，值为列的名称，查找列时通过在表中查找列名称实现
- 支付规则表(payment)定义了项目ID(project_id)到支付账号(project_account)的映射关系

## 数据验证

### 基础验证

- 表source中列employee_id必须存在
- 表source中需要拆分的列必须存在
- 表reference中列employee_id、project_id、project_category、project_hours必须存在
- 表payment中列project_id、project_account必须存在（可选，仅在配置文件中配置了payment时检查）

### 预检查（一次性收集所有问题）

1. 表reference按(employee_id, project_id)联合检索无重复数据，如有重复则报错（每个重复对仅报告一次）
2. 表payment按project_id无重复数据，如有重复则报错（每个重复ID仅报告一次）
3. 表payment中project_id非空时project_account字段不为空，如为空则报错
4. 表reference中project_id必须在表payment中有对应记录，如无则报错（仅当配置了payment时检查）
5. 表source中未参与拆分的行（在reference中无匹配employee_id），其project_id必须在表payment中有对应记录，如无则报错（仅当配置了payment时检查）
6. 表reference中employee_id不能为空，防止拆分时匹配失败
7. 表source中employee_id不能为空
8. 表reference中project_hours必须为数字值，非数字值无法计算拆分比例
9. 表reference中project_hours不能为负数
10. 表source和表reference的employee_id数据类型必须一致，防止字符串与数字混用导致匹配失败

所有验证错误一次性收集并输出，便于一次性修正。

## 拆分规则

- 以表source为基础，参考表reference进行拆分，拆分结果保存到表result中
- 表result与表source列的名称和顺序大致相同（会增加支付账号列）
- 表source中列employee_id和表reference中列employee_id是左连接关系，通过列的名称定位列
  - 如果通过employee_id在表reference中找到了对应的记录
    - 列project_id、project_category、project_hours内容按列名从表reference中获取
    - 配置文件input.splitting_columns中定义的行以表reference中列project_hours为准按比例进行拆分
    - 未在配置文件input.splitting_columns和input.sheet.source.columns中定义的列以表source为准保持不变
    - 表result中拆分后的行的数字格式同表source中拆分前的行
  - 如果通过employee_id在表reference中未找到对应的记录
    - 表source中该行整体复制到表result，包括该行的数字格式
- 拆分过程中如果遇到非数字 project_hours，报错退出并包含具体的 employee_id 和 project_id 上下文

## 合并规则

合并仅在配置文件中存在 payment 配置时执行。如未配置 payment，拆分结果直接输出，不合并，也不添加支付账号列。合并过程中 splitting_columns 索引会自动去重，防止重复计算。

拆分完成后，按支付账号对结果行进行合并：

1. **合并键**：(employee_id, project_account)，同一员工同一支付账号的拆分行合并
2. **合并范围**：仅在单个source行拆分结果内合并
3. **字段处理**：
   - project_id：逗号分隔的去重值，按出现顺序
   - project_category：逗号分隔的去重值，按出现顺序
   - project_hours：求和
   - project_account：从支付规则表获取
   - splitting_columns：求和
   - 其他列：保持不变

## 输出验证

处理完成并保存输出文件后，调用 `verify_output()` 进行完整性校验：

1. 输出文件是否存在并可打开
2. 结果表（result sheet）和源表（source sheet）是否存在于输出文件中
3. 结果表中是否有空行
4. 拆分列的值是否为数字且非负数
5. 总额一致性：结果表中每个拆分列的合计与源表中对应列的合计之差不超过 0.001

验证失败则报错退出。

## 测试用例

### 表头一致

```markdown 表reference
| 姓名 | 工号 | 费用类别 | 费用所属中心 | 实际出勤 |
|------|------|----------|--------------|----------|
```

```markdown 表source
| 姓名 | 工号 | 部门   | 基本工资  | 岗位工资  | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 |
|------|------|--------|-----------|-----------|----------|--------------|----------|----------|
```

```markdown 表result
| 姓名 | 工号 | 部门   | 基本工资  | 岗位工资 | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 | 支付账号 |
|------|------|--------|-----------|----------|----------|--------------|----------|----------|----------|
```

### 原样复制

```markdown 表reference
| 姓名 | 工号 | 费用类别 | 费用所属中心 | 实际出勤 |
|------|------|----------|--------------|----------|
```

```markdown 表source
| 姓名 | 工号 | 部门   | 基本工资  | 岗位工资  | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 |
|------|------|--------|-----------|-----------|----------|--------------|----------|----------|
| 张三 | AA   | 中国   | 1000.00   | 3000.00   | 研发     | 研发部       | 21       | BB       |
```

```markdown 表payment
| 费用所属中心 | 支付账号   |
|--------------|------------|
| 研发部       | Account_RD |
```

```markdown 表result
| 姓名 | 工号 | 部门   | 基本工资  | 岗位工资 | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 | 支付账号    |
|------|------|--------|-----------|----------|----------|--------------|----------|----------|-------------|
| 张三 | AA   | 中国   | 1000.00   | 3000.00  | 研发     | 研发部       | 21       | BB       | Account_RD  |
```

### 需要拆分（不合并）

```markdown 表reference
| 姓名 | 工号 | 费用类别 | 费用所属中心 | 实际出勤 |
|------|------|----------|--------------|----------|
| 张三 | AA   | 研发     | 1            | 1        |
| 张三 | AA   | 研发     | 2            | 4        |
| 张三 | AA   | 销售     | 3            | 4        |
```

```markdown 表source
| 姓名 | 工号 | 部门   | 基本工资  | 岗位工资  | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 |
|------|------|--------|-----------|-----------|----------|--------------|----------|----------|
| 张三 | AA   | 中国   | 1000.00   | 3000.00   | 研发     | 研发部       | 21       | BB       |
```

```markdown 表payment（各项目不同支付账号，不触发合并）
| 费用所属中心 | 支付账号  |
|--------------|-----------|
| 1            | Account1  |
| 2            | Account2  |
| 3            | Account3  |
```

```markdown 表result
| 姓名 | 工号 | 部门   | 基本工资  | 岗位工资 | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 | 支付账号  |
|------|------|--------|-----------|----------|----------|--------------|----------|----------|-----------|
| 张三 | AA   | 中国   | 111.11    | 333.33   | 研发     | 1            | 1        | BB       | Account1  |
| 张三 | AA   | 中国   | 444.44    | 1333.33  | 研发     | 2            | 4        | BB       | Account2  |
| 张三 | AA   | 中国   | 444.44    | 1333.33  | 销售     | 3            | 4        | BB       | Account3  |
```

### 需要合并

```markdown 表payment（项目1和2共享支付账号，触发合并）
| 费用所属中心 | 支付账号  |
|--------------|-----------|
| 1            | Account_X |
| 2            | Account_X |
| 3            | Account_Y |
```

```markdown 表result
| 姓名 | 工号 | 部门   | 基本工资  | 岗位工资 | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 | 支付账号   |
|------|------|--------|-----------|----------|----------|--------------|----------|----------|------------|
| 张三 | AA   | 中国   | 555.55    | 1666.66  | 研发     | 1,2          | 5        | BB       | Account_X  |
| 张三 | AA   | 中国   | 444.44    | 1333.33  | 销售     | 3            | 4        | BB       | Account_Y  |
```
