Sub SplitSalaryByProjectHours()
    Dim wsSource As Worksheet, wsDest As Worksheet, wsRef As Worksheet
    Dim dict As Object, lastRow As Long, srcData As Variant, results()
    Dim empProjects As Collection, totalHours As Double
    Dim i As Long, j As Long, k As Long, m As Long, resultRow As Long
    
    Set dict = CreateObject("Scripting.Dictionary")
    Set wsSource = ThisWorkbook.Sheets("工资")
    Set wsDest = ThisWorkbook.Sheets("工资拆分")
    Set wsRef = ThisWorkbook.Sheets("工时")
    
    ' 清除目标表原有数据
    wsDest.Cells.ClearContents
    
    ' 读取参考表数据到字典
    lastRow = wsRef.Cells(wsRef.Rows.Count, 2).End(xlUp).Row
    For i = 2 To lastRow
        Dim empId As String, proj As Variant
        empId = wsRef.Cells(i, 2).Value
        proj = Array(wsRef.Cells(i, 4).Value, wsRef.Cells(i, 3).Value, wsRef.Cells(i, 5).Value)
        
        If Not dict.Exists(empId) Then
            dict.Add empId, New Collection
        End If
        dict(empId).Add proj
    Next i
    
    ' 读取源表数据
    lastRow = wsSource.Cells(wsSource.Rows.Count, 2).End(xlUp).Row
    srcData = wsSource.Range("A1:H" & lastRow).Value
    
    ' 初始化结果数组
    ReDim results(1 To UBound(srcData) * 5, 1 To UBound(srcData, 2))
    
    ' 处理每一行数据
    For i = 2 To UBound(srcData)
        resultRow = resultRow + 1
        empId = srcData(i, 2)
        
        If dict.Exists(empId) Then
            ' 计算总工时
            totalHours = 0
            For Each proj In dict(empId)
                totalHours = totalHours + proj(2)
            Next
            
            ' 拆分到各个项目
            For Each proj In dict(empId)
                For j = 1 To UBound(srcData, 2)
                    results(resultRow, j) = srcData(i, j)
                Next
                
                ' 更新项目相关字段
                results(resultRow, 4) = proj(1) ' 费用分类
                results(resultRow, 5) = proj(0) ' 费用所属中心
                
                ' 计算拆分后的工资
                If totalHours > 0 Then
                    results(resultRow, 7) = Round(srcData(i, 7) * (proj(2) / totalHours), 2)
                    results(resultRow, 8) = Round(srcData(i, 8) * (proj(2) / totalHours), 2)
                End If
                
                resultRow = resultRow + 1
            Next
            resultRow = resultRow - 1
        Else
            ' 直接复制原始数据
            For j = 1 To UBound(srcData, 2)
                results(resultRow, j) = srcData(i, j)
            Next
        End If
    Next i
    
    ' 写入目标表并保留格式
    With wsDest
        .Range("A1:H1").Value = wsSource.Range("A1:H1").Value
        .Range("A2").Resize(resultRow, UBound(results, 2)).Value = results
        .Columns.AutoFit
    End With
    
    MsgBox "处理完成，共生成 " & resultRow & " 条记录！"
End Sub
