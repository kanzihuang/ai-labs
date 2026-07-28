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
      name: "支付规则"
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

## 编程规范

- 编写语言为python，要求按python编程规范编写程序
- 默认从配置文件中读取配置，配置文件路径可通过命令行参数设定
- 检查输入文件，如果无法拆分直接退出，并输出无法拆分的原因
- 文件编码方式采用统一采用UTF8

## 数据描述

- 配置文件input.splitting_columns下的键值对表示需要拆分的列
- 配置文件input.sheet.*.columns下的键值对表示处理过程中涉及到的列，键为列的标识，值为列的名称，查找列时通过在表中查找列名称实现
- 支付规则表(payment)定义了项目ID(project_id)到支付账号(project_account)的映射关系

## 数据验证

### 基础验证

- 表source中列employee_id必须存在
- 表source中需要拆分的列必须存在
- 表reference中列employee_id、project_id、project_category、project_hours必须存在
- 表payment中列project_id、project_account必须存在

### 预检查（一次性收集所有问题）

1. 表reference按(employee_id, project_id)联合检索无重复数据，如有重复则报错
2. 表payment按project_id无重复数据，如有重复则报错
3. 表payment中project_id非空时project_account字段不为空，如为空则报错
4. 表reference中project_id必须在表payment中有对应记录，如无则报错
5. 表source中未参与拆分的行（在reference中无匹配employee_id），其project_id必须在表payment中有对应记录，如无则报错

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

## 合并规则

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
