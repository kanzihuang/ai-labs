# Excel Splitter

一个用于拆分Excel表格中工资数据的工具，根据工时表对工资进行按比例拆分，可选按支付账号合并。

## 功能说明

该工具用于处理工资数据，主要功能包括：

1. 根据工时表对工资进行按比例拆分
2. 根据支付规则表为每行填充支付账号
3. 可选按支付账号合并同一员工的行（通过 `merge_by_payment_account` 配置）
4. 保持源表格的格式和样式
5. 支持自定义配置的列映射和拆分规则

## 配置说明

配置文件采用YAML格式，默认文件名为`config.yaml`。配置项说明如下：

- `merge_by_payment_account`（默认 `false`）：设为 `true` 时将同一员工同一支付账号的拆分行合并为一行
- `input.sheet.*.columns` 下的键值对表示处理过程中涉及到的列，键为列的标识，值为列的名称，查找列时通过列名称在表头中定位
- `input.splitting_columns` 下的列表表示需要按比例拆分的列
- `input.computed_columns`（可选）：拆分后按公式计算派生列。键为列名，值为公式表达式。按定义顺序依次计算，后续公式可引用前面的计算结果。公式支持 `+ - * / ( )` 运算符，引用的列名必须在 `splitting_columns` 或前面的计算列中。仅对已拆分的行进行计算，未拆分的行保留源表原始值
- `input.sheet.*.null_check_columns`（可选）：按表（source/reference/payment）定义需检测空值的列名列表。列名为 Excel 实际表头名。空值定义：`None`、空字符串 `""`、纯空白字符串。数字 `0` / `0.0` 不算空值。检测到空值时收集所有错误并中断处理。每行每列独立报告，仅表头的空表不报错，全 `None` 的格式行自动跳过
- 支付规则表(payment)定义了（公司/employer_name，费用所属中心/project_id）联合键到支付账号的映射关系，为**必需配置**，用于填充每行的支付账号
- `keep_style`（默认 `true`）：设为 `false` 时跳过样式复制，写入速度可提升 45x 以上。适合不需要保留原格式的场景
- `write_batch_size`（默认 `500`）：控制批量写入大小和进度输出频率。值越大内存占用稍多，但对写入速度影响很小

```yaml
# 合并选项（默认 false，即不合并）
merge_by_payment_account: false

# 性能选项（可选，均有默认值）
keep_style: true          # 是否保留原格式。false 可大幅提速
write_batch_size: 500     # 写入批次大小，也用作进度输出间隔

# 注意：payment 表为必需配置，source.columns 中必须包含 employer_name 和 payment_account
input:
  path: "input/项目成本.xlsx"  # 输入文件路径
  sheet:
    source:
      name: "输入-工资表"  # 源数据表名
      columns:  # 源数据列映射
        employee_id: "工号"
        project_id: "费用所属中心"
        project_category: "费用类别"
        project_hours: "实际出勤"
        employer_name: "公司"
        payment_account: "支付账号"
    reference:
      name: "输入-工时表"  # 参考数据表名
      columns:  # 参考数据列映射
        employee_id: "工号"
        project_id: "费用所属中心"
        project_category: "费用类别"
        project_hours: "实际出勤"
    payment:
      name: "输入-支付规则"  # 支付规则表（必需）
      columns:  # 支付规则列映射
        employer_name: "公司"
        project_id: "费用所属中心"
        payment_account: "支付账号"
  splitting_columns:  # 需要拆分的列，重复条目会被检测并报错
  - 基本工资
  - 岗位工资
  - 用餐补助
  - 差旅补助
  computed_columns:     # 可选：拆分后按公式计算（按定义顺序依次计算）
    福利前工资合计: "基本工资 + 岗位工资"
    税前应发工资总额(不含差补): "福利前工资合计 + 用餐补助"
    实发工资: "税前应发工资总额(不含差补) + 差旅补助"
output:
  path: "output/项目成本拆分.xlsx"  # 输出文件路径
  sheet:
    result:
      name: "工资拆分"  # 结果表名
```

## 配置验证

在处理开始之前，程序调用 `validate_config()` 对配置文件的结构进行校验：

1. **必填键检查**：
   - `input.path` — 输入文件路径，不能为空
   - `input.sheet.source` — 源数据表配置
   - `input.sheet.source.columns.employee_id` — 源表 employee_id 列映射
   - `input.sheet.reference` — 参考数据表配置
   - `input.sheet.reference.columns` 下的四个必填字段（`employee_id`、`project_id`、`project_category`、`project_hours`）
   - `input.splitting_columns` — 拆分列列表，必须为非空列表，重复条目会报错
   - `input.sheet.*.null_check_columns` — 可选，必须是元素为非空字符串的非空列表，重复条目会报错
   - `output.path` — 输出文件路径，不能为空
   - `output.sheet.result.name` — 结果表名称，不能为空

2. **payment 表必需性**：
   - payment 配置项为必需；必须包含有效的 `name`、`columns.employer_name`、`columns.project_id` 和 `columns.payment_account`
   - `source.columns` 中也必须包含 `employer_name` 和 `payment_account`
   - 缺少 payment 配置或配置不完整则报错退出

3. **merge_by_payment_account**：
   - 可选配置，默认为 `false`（不合并）
   - 设为 `true` 时，同一员工同一支付账号的拆分行将合并为一行

4. **splitting_columns 去重**：
   - 检测 `splitting_columns` 中的重复条目并报错
   - 合并阶段也会自动去重，防止重复计算

所有配置错误一次性收集并输出。

## 数据处理流程

1. **配置验证** — 调用 `validate_config()` 验证配置文件结构和类型
2. **基础验证** — 验证输入文件、必需 sheet 和列是否存在（payment 表为必需）
3. **预检查** — 一次性收集所有数据质量问题（详见[数据验证规则]）
4. **拆分** — 根据工时表按比例拆分工资数据
5. **填充支付账号** — 为每行根据 `(employer_name, project_id)` 查找并填充 `payment_account`
6. **合并** — 如果 `merge_by_payment_account: true`，将同一员工同一支付账号的拆分行合并
7. **输出验证** — 保存后调用 `verify_output()` 验证输出文件完整性

## 输出验证

在文件保存后，程序调用 `verify_output()` 对输出文件进行完整性校验：

1. **文件有效性** — 输出文件是否存在、能否正常打开
2. **Sheet 完整性** — 结果表和源表是否都在输出文件中
3. **空行检查** — 结果表中不能有空行
4. **数值有效性** — 拆分列的值必须为数字且不能为负数
5. **总额一致性** — 结果表中每个拆分列的合计与源表中对应列的合计之差不超过 0.001

任何验证失败会立即报错退出。

## 数据验证规则

### 基础验证

1. 源数据表(source)验证：
   - 必须包含`employee_id`列
   - 必须包含`splitting_columns`中定义的所有列

2. 参考数据表(reference)验证：
   - 必须包含`employee_id`列
   - 必须包含`project_id`列
   - 必须包含`project_category`列
   - 必须包含`project_hours`列

3. 支付规则表(payment)验证（必需）：
   - payment 配置为必需项，必须包含`employer_name`、`project_id`和`payment_account`列
   - `source.columns` 中也必须包含 `employer_name` 和 `payment_account`
   - 程序会为每行填充支付账号，结果表中始终包含支付账号列

### 预检查（所有问题一次性报告）

| 检查项 | 规则 | 说明 |
|--------|------|------|
| 工时表唯一性 | 按`(employee_id, project_id)`联合检索无重复 | 同一员工同一项目的工时记录不能重复（每个重复对仅报告一次） |
| 支付规则唯一性 | 按`(employer_name, project_id)`联合键无重复 | 同一公司同一项目只能有一个支付账号（每个重复对仅报告一次） |
| 支付账号完整性 | `project_id`非空时`payment_account`不能为空 | 每个有值的项目ID都必须有对应支付账号 |
| 工时表项目覆盖 | `(employer_name, project_id)`必须在支付规则表中存在 | 拆分后的项目来自工时表，必须能查到支付账号 |
| 源表非拆分覆盖 | 无参考匹配的源行`(employer_name, project_id)`必须在支付规则表中存在 | 未拆分的行保留原项目，必须能查到支付账号 |
| 拆分覆盖 | 拆分后行的`(employer_name, reference_project_id)`必须在支付规则表中存在 | 拆分后取工时表项目对应的支付账号 |
| 空 employee_id (参考表) | 参考表中 employee_id 不能为空 | 防止拆分时匹配失败 |
| 空 employee_id (源表) | 源表中 employee_id 不能为空 | 防止拆分时匹配失败 |
| 非数字工时 | 工时表的`project_hours`列必须为数字 | 非数字值无法计算拆分比例 |
| 负工时 | 工时表的`project_hours`不能为负数 | 负工时导致不合理的拆分结果 |
| 类型不一致 | 源表和参考表的 employee_id 类型必须一致 | 防止字符串与数字混用导致匹配失败 |

所有验证错误会一次性收集并输出，便于一次性修正。

## 拆分规则

1. 以源数据表(source)为基础，参考工时表(reference)进行拆分
2. 通过`employee_id`（工号）进行左连接匹配：
   - 如果找到匹配记录：
     - 更新`project_id`、`project_category`、`project_hours`列的内容（来自工时表）
     - 对`splitting_columns`中定义的列按`project_hours`比例进行拆分
     - 其他列保持源数据不变
   - 如果未找到匹配记录：
     - 直接复制源数据行到结果表

- 如果在拆分过程中遇到非数字工时值，会立即报错并提示具体的 employee_id 和 project_id 上下文

## 合并规则

合并仅在 `merge_by_payment_account: true` 时执行。无论是否合并，每行都会填充支付账号。

当启用合并时，拆分完成后按支付账号对结果行进行合并：

1. **合并键**：`employee_id + payment_account`
   - 同一员工、同一支付账号的拆分行合并为一行
   - 不同员工即使支付账号相同也互不合并

2. **合并范围**：仅在单个源数据行的拆分结果内合并
   - 不同源数据行之间不会合并

3. **字段处理**：

| 字段 | 合并后取值 |
|------|-----------|
| `project_id` | 逗号分隔的去重值，按出现顺序 |
| `project_category` | 逗号分隔的去重值，按出现顺序 |
| `project_hours` | 求和 |
| `payment_account` | 已在填充阶段设置，保持不变 |
| 拆分列（splitting_columns） | 求和 |
| 其他列 | 保持不变（同一员工值相同） |

当不合并时（默认），每行保留独立的 `project_id`，`payment_account` 根据该行的 `(employer_name, project_id)` 填充。

## 使用说明

1. 准备配置文件`config.yaml`
2. 准备输入Excel文件，确保包含必要的sheet和列：
   - 源数据表（工资数据）
   - 参考数据表（工时数据）
   - 支付规则表（公司+项目与支付账号的对应关系）
3. 运行程序：
   ```bash
   python main.py [--config config.yaml]
   ```

## 编程规范

- 编写语言为 Python，遵循 Python 编程规范
- 默认从配置文件读取配置，配置文件路径通过 `--config` 命令行参数指定
- 首先调用 `validate_config()` 验证配置文件结构，有误则直接退出并输出详细原因
- 然后检查输入文件，无法拆分则直接退出并输出原因
- 所有数据验证错误一次性收集并输出
- 处理完成后调用 `verify_output()` 验证输出文件完整性
- 文件编码统一采用 UTF-8

## 打包

将程序打包为独立可执行文件（无需安装 Python 即可运行）。

```bash
# 安装 virtualenv 并创建虚拟环境
pip install virtualenv
virtualenv venv

# 激活虚拟环境（Windows）
venv\Scripts\activate.bat
# 或激活虚拟环境（Linux/macOS）
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装 PyInstaller
pip install pyinstaller

# 打包为单个 exe 文件
pyinstaller --onefile main.py

# 退出虚拟环境
deactivate
```

打包后的文件位于 `dist/main.exe`（Windows）或 `dist/main`（Linux/macOS）。将 `config.yaml` 和输入 Excel 文件放在同一目录下即可运行。

## 测试用例

### 1. 表头一致性测试

验证结果表的表头与源数据表一致（含新增的支付账号列）。

```markdown
表source:
| 姓名 | 工号 | 部门 | 基本工资 | 岗位工资 | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 |

表result:
| 姓名 | 工号 | 部门 | 基本工资 | 岗位工资 | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 | 支付账号 |
```

### 2. 无匹配记录测试

当工号在参考表中无匹配记录时，直接复制源数据行，并填充支付账号。

```markdown
表source:
| 姓名 | 工号 | 部门 | 基本工资 | 岗位工资 | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 |
|------|------|------|----------|----------|----------|--------------|----------|----------|
| 张三 | AA   | 中国 | 1000.00  | 3000.00  | 研发     | 研发部       | 21       | BB       |

表result:
| 姓名 | 工号 | 部门 | 基本工资 | 岗位工资 | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 | 支付账号   |
|------|------|------|----------|----------|----------|--------------|----------|----------|------------|
| 张三 | AA   | 中国 | 1000.00  | 3000.00  | 研发     | 研发部       | 21       | BB       | Account_RD |
```

### 3. 工资拆分测试（不合并）

当各项目的支付账号各不相同时，拆分后不合并。

```markdown
表source:
| 姓名 | 工号 | 部门 | 基本工资 | 岗位工资 | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 |
|------|------|------|----------|----------|----------|--------------|----------|----------|
| 张三 | AA   | 中国 | 1000.00  | 3000.00  | 研发     | 研发部       | 21       | BB       |

表reference:
| 姓名 | 工号 | 费用类别 | 费用所属中心 | 实际出勤 |
|------|------|----------|--------------|----------|
| 张三 | AA   | 研发     | 1            | 1        |
| 张三 | AA   | 研发     | 2            | 4        |
| 张三 | AA   | 销售     | 3            | 4        |

表payment:
| 公司 | 费用所属中心 | 支付账号  |
|------|--------------|-----------|
| ABC  | 1            | Account1  |
| ABC  | 2            | Account2  |
| ABC  | 3            | Account3  |

表result:
| 姓名 | 工号 | 部门 | 基本工资 | 岗位工资 | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 | 支付账号  |
|------|------|------|----------|----------|----------|--------------|----------|----------|-----------|
| 张三 | AA   | 中国 | 111.11   | 333.33   | 研发     | 1            | 1        | BB       | Account1  |
| 张三 | AA   | 中国 | 444.44   | 1333.33  | 研发     | 2            | 4        | BB       | Account2  |
| 张三 | AA   | 中国 | 444.44   | 1333.33  | 销售     | 3            | 4        | BB       | Account3  |
```

### 4. 支付账号合并测试

当多个项目共享同一支付账号时，拆分行合并。

```markdown
表payment:
| 公司 | 费用所属中心 | 支付账号   |
|------|--------------|-----------|
| ABC  | 1            | Account_X |
| ABC  | 2            | Account_X |
| ABC  | 3            | Account_Y |

表result:
| 姓名 | 工号 | 部门 | 基本工资 | 岗位工资 | 费用类别 | 费用所属中心 | 实际出勤 | 分管领导 | 支付账号   |
|------|------|------|----------|----------|----------|--------------|----------|----------|------------|
| 张三 | AA   | 中国 | 555.55   | 1666.66  | 研发     | 1,2          | 5        | BB       | Account_X  |
| 张三 | AA   | 中国 | 444.44   | 1333.33  | 销售     | 3            | 4        | BB       | Account_Y  |
```

## 运行测试

```bash
python3 -m unittest test_excel_splitter.py -v
```

## 注意事项

1. 所有文件编码采用UTF-8
2. 输入文件必须符合数据验证规则，所有问题会一次性报告
3. 拆分比例基于参考表中的总工时计算
4. 支付账号合并仅在单个源行拆分结果内进行
5. 支付规则表（payment）为必需配置，程序会自动在结果表中添加支付账号列（如果源表中没有）

## 项目结构

```
excel-splitter/
├── input/              # 输入文件目录
├── output/             # 输出文件目录
├── main.py             # 主程序
├── test_excel_splitter.py  # 单元测试
├── config.yaml         # 配置文件
├── requirements.txt    # 项目依赖
└── README.md           # 项目文档
```

## 依赖

- Python 3.6+
- openpyxl
- pyyaml

## 错误处理

- 配置文件结构错误 → 在 `validate_config()` 阶段报错退出（不读取输入文件）
- 输入文件不存在 → 报错退出
- Sheet 或列缺失 → 报错退出
- 数据重复或缺失 → 在预检查阶段收集所有问题后一次性报告
- 数据质量问题（空 employee_id、非数字工时、负工时、类型不一致） → 在预检查阶段一次性报告
- 拆分过程中发现非数字工时 → 报错退出，包含 employee_id/project_id 上下文
- 输出文件验证失败（空行、负值、非数字、总额不一致） → 在 `verify_output()` 阶段报错退出
- 所有错误信息均打印到控制台
