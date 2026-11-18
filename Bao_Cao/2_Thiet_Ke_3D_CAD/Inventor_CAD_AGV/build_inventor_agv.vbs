' ============================================================================
' AUTODESK INVENTOR 2027 COM AUTOMATION SCRIPT
' Tu dong dung Mo Hinh 3D Chi Tiet (.IPT) va Ban Ve Lap (.IAM) truc tiep trong
' phan mem Autodesk Inventor 2027 cho Du An Xe Tu Hanh AGV Xe Tai Dau Vuong!
' ============================================================================

Option Explicit

Const kPartDocumentObject = 12290
Const kAssemblyDocumentObject = 12291
Const kPositiveExtentDirection = 20993
Const kNegativeExtentDirection = 20994
Const kSymmetricExtentDirection = 20995
Const kJoinOperation = 20481
Const kCutOperation = 20482
Const kNewBodyOperation = 20485
Const kShadedWithEdgesRendering = 8964

Dim invApp, tg, fso, outDir, wsh
Set invApp = Nothing
Set fso = CreateObject("Scripting.FileSystemObject")
Set wsh = CreateObject("WScript.Shell")

outDir = "E:\agv_server\Inventor_CAD_Files"
If Not fso.FolderExists(outDir) Then
    fso.CreateFolder(outDir)
End If

WScript.Echo "============================================================================"
WScript.Echo "   HE THONG TU DONG VE 3D CAD TRUC TIEP TRONG AUTODESK INVENTOR 2027"
WScript.Echo "============================================================================"

On Error Resume Next
Set invApp = GetObject(, "Inventor.Application")
If Not IsObject(invApp) Then Set invApp = Nothing
If Err.Number <> 0 Or (invApp Is Nothing) Then
    Err.Clear
    WScript.Echo "[*] Dang ket noi / khoi dong Autodesk Inventor 2027..."
    Set invApp = CreateObject("Inventor.Application")
    If Not IsObject(invApp) Then Set invApp = Nothing
End If
On Error GoTo 0

If invApp Is Nothing Then
    WScript.Echo "[!] LOI: Khong the ket noi voi Autodesk Inventor 2027!"
    WScript.Echo "    Hay mo san phan mem Autodesk Inventor 2027 len truoc roi chay lai file nay!"
    WScript.Quit 1
End If

' Doi den khi Inventor 2027 nap xong giao dien (invApp.Ready = True)
On Error Resume Next
Dim readyWait
For readyWait = 1 To 40
    If invApp.Ready Then Exit For
    WScript.Sleep 1000
Next
invApp.Visible = True
invApp.SilentOperation = True
Set tg = invApp.TransientGeometry
On Error GoTo 0

WScript.Echo "[+] DA KET NOI THANH CONG VOI: " & invApp.Caption
WScript.Echo "[*] Thu muc luu cac file .IPT va .IAM: " & outDir
WScript.Echo ""

' Quy doi milimet (mm) sang centimet (cm - don vi noi bo cua Inventor API)
Function mm(val)
    mm = CDbl(val) / 10.0
End Function

' Ham dat mau sac cho Part trong Inventor
Sub SetPartColorRGB(doc, r, g, b)
    On Error Resume Next
    Dim newAsset, colorVal
    Set newAsset = Nothing
    Set colorVal = Nothing
    Set newAsset = doc.AppearanceAssets.Add("Generic")
    If Not (newAsset Is Nothing) Then
        Set colorVal = newAsset.Item("generic_diffuse")
        If Not (colorVal Is Nothing) Then
            colorVal.Value = invApp.TransientObjects.CreateColor(r, g, b)
        End If
        doc.ActiveAppearance = newAsset
    End If
    On Error GoTo 0
End Sub

' Ham tao khoi hop 3D (Box) tu (x1, y1, z1) den (x2, y2, z2) tinh bang mm
' He truc: X = Chieu doc xe, Y = Chieu ngang xe, Z = Chieu cao xe
Sub AddBoxMM(compDef, x1, y1, z1, x2, y2, z2, isCut)
    On Error Resume Next
    Dim wp, sk, p1, p2, prof, ext
    ' WorkPlanes.Item(3) la mat phang XY (Z = 0)
    Set wp = compDef.WorkPlanes.AddByPlaneAndOffset(compDef.WorkPlanes.Item(3), mm(z1), False)
    wp.Visible = False
    Set sk = compDef.Sketches.Add(wp)
    Set p1 = tg.CreatePoint2d(mm(x1), mm(y1))
    Set p2 = tg.CreatePoint2d(mm(x2), mm(y2))
    Call sk.SketchLines.AddAsTwoPointRectangle(p1, p2)
    Set prof = sk.Profiles.AddForSolid()
    
    Dim dist
    dist = mm(Abs(z2 - z1))
    If dist < 0.005 Then dist = 0.01

    If isCut Then
        Set ext = compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, kPositiveExtentDirection, kCutOperation)
    Else
        Err.Clear
        Set ext = compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, kPositiveExtentDirection, kJoinOperation)
        If Err.Number <> 0 Then
            Err.Clear
            Set ext = compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, kPositiveExtentDirection, kNewBodyOperation)
        End If
    End If
    On Error GoTo 0
End Sub

' Ham tao khoi tru tron (Cylinder) doc theo truc Z (tu z1 den z2, tam cx, cy, ban kinh r_mm)
Sub AddCylZ_MM(compDef, cx, cy, z1, z2, r_mm, isCut)
    On Error Resume Next
    Dim wp, sk, pt, prof, ext, dist
    Set wp = compDef.WorkPlanes.AddByPlaneAndOffset(compDef.WorkPlanes.Item(3), mm(z1), False)
    wp.Visible = False
    Set sk = compDef.Sketches.Add(wp)
    Set pt = tg.CreatePoint2d(mm(cx), mm(cy))
    Call sk.SketchCircles.AddByCenterRadius(pt, mm(r_mm))
    Set prof = sk.Profiles.AddForSolid()
    dist = mm(Abs(z2 - z1))
    If isCut Then
        Set ext = compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, kPositiveExtentDirection, kCutOperation)
    Else
        Err.Clear
        Set ext = compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, kPositiveExtentDirection, kJoinOperation)
        If Err.Number <> 0 Then
            Err.Clear
            Set ext = compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, kPositiveExtentDirection, kNewBodyOperation)
        End If
    End If
    On Error GoTo 0
End Sub

' Ham tao thanh Sat V Lo (L-Angle Slotted Bar) doc theo truc X tu x1 den x2
Sub AddSlottedVBarX(compDef, x1, x2, y0, z0, vSize, vThick, punchHoles)
    Call AddBoxMM(compDef, x1, y0, z0, x2, y0 + vSize, z0 + vThick, False)
    Call AddBoxMM(compDef, x1, y0, z0, x2, y0 + vThick, z0 + vSize, False)
    If punchHoles Then
        Dim hx
        For hx = x1 + 15 To x2 - 15 Step 25
            Call AddCylZ_MM(compDef, hx, y0 + vSize * 0.55, z0 - 1, z0 + vThick + 1, 3.2, True)
        Next
    End If
End Sub

' Ham tao thanh Sat V Lo doc theo truc Y (Dam ngang) tu y1 den y2
Sub AddSlottedVBarY(compDef, x0, y1, y2, z0, vSize, vThick, punchHoles)
    Call AddBoxMM(compDef, x0, y1, z0, x0 + vSize, y2, z0 + vThick, False)
    Call AddBoxMM(compDef, x0, y1, z0, x0 + vThick, y2, z0 + vSize, False)
    If punchHoles Then
        Dim hy
        For hy = y1 + 15 To y2 - 15 Step 25
            Call AddCylZ_MM(compDef, x0 + vSize * 0.55, hy, z0 - 1, z0 + vThick + 1, 3.2, True)
        Next
    End If
End Sub

' Ham tao thanh Sat V Lo dung doc theo truc Z (Tru dung) tu z1 den z2
Sub AddSlottedVBarZ(compDef, x0, y0, z1, z2, vSize, vThick)
    Call AddBoxMM(compDef, x0, y0, z1, x0 + vSize, y0 + vThick, z2, False)
    Call AddBoxMM(compDef, x0, y0, z1, x0 + vThick, y0 + vSize, z2, False)
End Sub

' Ham tao 1 con Servo MG996R chuan ban ve (40.3 x 20.0 x 36.6 mm, tai 53.6mm, nhong dong 25T)
Sub AddMG996RAt(compDef, cx, cy, zBase)
    Call AddBoxMM(compDef, cx - 30.15, cy - 10.0, zBase, cx + 10.15, cy + 10.0, zBase + 36.6, False)
    Call AddBoxMM(compDef, cx - 36.8, cy - 9.75, zBase + 26.6, cx + 16.8, cy + 9.75, zBase + 29.1, False)
    Call AddCylZ_MM(compDef, cx, cy, zBase + 36.6, zBase + 40.6, 6.0, False)
    Call AddCylZ_MM(compDef, cx, cy, zBase + 40.6, zBase + 47.6, 3.0, False)
    Call AddCylZ_MM(compDef, cx, cy, zBase + 45.5, zBase + 48.0, 10.0, False)
End Sub

Dim templatePart, templateAssy
templatePart = invApp.FileManager.GetTemplateFile(kPartDocumentObject)
templateAssy = invApp.FileManager.GetTemplateFile(kAssemblyDocumentObject)

' ============================================================================
' PART 1: KHUNG XE TAI SAT V LO CO 4 HOC RANH BANH XE (350 x 250 mm)
' ============================================================================
WScript.Echo "[1/6] Dang ve Part 1: 01_Khung_Sat_V_Lo_Co_Hoc_Banh.ipt ..."
Dim docFrame, defFrame, pathFrame
pathFrame = outDir & "\01_Khung_Sat_V_Lo_Co_Hoc_Banh.ipt"
If fso.FileExists(pathFrame) Then fso.DeleteFile(pathFrame)
Set docFrame = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
Set defFrame = docFrame.ComponentDefinition

Call AddSlottedVBarX(defFrame, 0, 350, 45, 30, 25, 2.0, True)
Call AddSlottedVBarX(defFrame, 0, 350, 180, 30, 25, 2.0, True)

Call AddSlottedVBarY(defFrame, 0, 0, 250, 30, 25, 2.0, True)
Call AddSlottedVBarY(defFrame, 113, 0, 250, 30, 25, 2.0, True)
Call AddSlottedVBarY(defFrame, 212, 0, 250, 30, 25, 2.0, True)
Call AddSlottedVBarY(defFrame, 325, 0, 250, 30, 25, 2.0, True)

Call AddSlottedVBarX(defFrame, 113, 237, 0, 30, 25, 2.0, False)
Call AddSlottedVBarX(defFrame, 113, 237, 225, 30, 25, 2.0, False)

Call AddSlottedVBarY(defFrame, 120, 45, 205, 32, 20, 2.0, False)
Call AddSlottedVBarY(defFrame, 260, 45, 205, 32, 20, 2.0, False)

Call AddSlottedVBarX(defFrame, 0, 350, 0, 50, 25, 2.0, True)
Call AddSlottedVBarX(defFrame, 0, 350, 225, 50, 25, 2.0, True)
Call AddSlottedVBarY(defFrame, 0, 0, 250, 50, 25, 2.0, False)
Call AddSlottedVBarY(defFrame, 100, 0, 250, 50, 25, 2.0, False)
Call AddSlottedVBarY(defFrame, 325, 0, 250, 50, 25, 2.0, False)

Call AddSlottedVBarZ(defFrame, 0, 0, 75, 175, 25, 2.0)
Call AddSlottedVBarZ(defFrame, 0, 225, 75, 175, 25, 2.0)
Call AddSlottedVBarZ(defFrame, 75, 0, 75, 175, 25, 2.0)
Call AddSlottedVBarZ(defFrame, 75, 225, 75, 175, 25, 2.0)

Call AddSlottedVBarX(defFrame, 0, 100, 0, 150, 25, 2.0, False)
Call AddSlottedVBarX(defFrame, 0, 100, 225, 150, 25, 2.0, False)
Call AddSlottedVBarX(defFrame, 0, 100, 88, 150, 25, 2.0, True)
Call AddSlottedVBarX(defFrame, 0, 100, 137, 150, 25, 2.0, True)
Call AddSlottedVBarY(defFrame, 0, 0, 250, 150, 25, 2.0, False)
Call AddSlottedVBarY(defFrame, 75, 0, 250, 150, 25, 2.0, False)

Call AddSlottedVBarX(defFrame, 100, 350, 0, 100, 25, 2.0, True)
Call AddSlottedVBarX(defFrame, 100, 350, 225, 100, 25, 2.0, True)
Call AddSlottedVBarZ(defFrame, 325, 0, 75, 125, 25, 2.0)
Call AddSlottedVBarZ(defFrame, 325, 225, 75, 125, 25, 2.0)
Call AddSlottedVBarY(defFrame, 325, 0, 250, 100, 25, 2.0, False)

Call SetPartColorRGB(docFrame, 55, 65, 81)
Call docFrame.SaveAs(pathFrame, False)

' ============================================================================
' PART 2: CUM 4 BANH MECANUM 80MM + 4 MOTOR XANH 1:90 + GA G140 TRONG HOC BANH
' ============================================================================
WScript.Echo "[2/6] Dang ve Part 2: 02_Cum_4_Banh_Mecanum80_Va_Motor_1_90.ipt ..."
Dim docWheels, defWheels, pathWheels
pathWheels = outDir & "\02_Cum_4_Banh_Mecanum80_Va_Motor_1_90.ipt"
If fso.FileExists(pathWheels) Then fso.DeleteFile(pathWheels)
Set docWheels = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
Set defWheels = docWheels.ComponentDefinition

Sub AddWheelAndMotorSub(compDef, wx, wy, isLeftSide)
    Dim yStart, yEnd
    If isLeftSide Then
        yStart = wy
        yEnd = wy + 38
        Call AddBoxMM(compDef, wx - 11.25, yEnd + 2, 30.6, wx + 11.25, yEnd + 44, 49.4, False)
        Call AddBoxMM(compDef, wx - 9.0, yEnd + 44, 31.5, wx + 9.0, yEnd + 72, 48.5, False)
        Call AddBoxMM(compDef, wx - 13.5, yEnd + 8, 29.0, wx + 13.5, yEnd + 28, 52.0, False)
    Else
        yStart = wy - 38
        yEnd = wy
        Call AddBoxMM(compDef, wx - 11.25, yStart - 44, 30.6, wx + 11.25, yStart - 2, 49.4, False)
        Call AddBoxMM(compDef, wx - 9.0, yStart - 72, 31.5, wx + 9.0, yStart - 44, 48.5, False)
        Call AddBoxMM(compDef, wx - 13.5, yStart - 28, 29.0, wx + 13.5, yStart - 8, 52.0, False)
    End If

    Call AddBoxMM(compDef, wx - 38, yStart, 12, wx + 38, yEnd, 68, False)
    Call AddBoxMM(compDef, wx - 28, yStart, 2, wx + 28, yEnd, 78, False)
    Call AddBoxMM(compDef, wx - 40, yStart + 4, 22, wx + 40, yEnd - 4, 58, False)
    Call AddBoxMM(compDef, wx - 3.5, yStart - 5, 36.5, wx + 3.5, yEnd + 5, 43.5, False)
End Sub

Call AddWheelAndMotorSub(defWheels, 65, 2, True)
Call AddWheelAndMotorSub(defWheels, 65, 248, False)
Call AddWheelAndMotorSub(defWheels, 285, 2, True)
Call AddWheelAndMotorSub(defWheels, 285, 248, False)

Call SetPartColorRGB(docWheels, 245, 158, 11)
Call docWheels.SaveAs(pathWheels, False)

' ============================================================================
' PART 3: BO MACH PCB CHINH 150x90mm (CHUAN GERBER ALTIUM) + KHOI PIN 3S 12V
' ============================================================================
WScript.Echo "[3/6] Dang ve Part 3: 03_Bo_Mach_PCB_150x90_Altium.ipt ..."
Dim docPCB, defPCB, pathPCB
pathPCB = outDir & "\03_Bo_Mach_PCB_150x90_Altium.ipt"
If fso.FileExists(pathPCB) Then fso.DeleteFile(pathPCB)
Set docPCB = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
Set defPCB = docPCB.ComponentDefinition

Dim pcbX0, pcbY0, pcbZ0
pcbX0 = 125 : pcbY0 = 55 : pcbZ0 = 44

Call AddBoxMM(defPCB, pcbX0, pcbY0, pcbZ0, pcbX0 + 150, pcbY0 + 90, pcbZ0 + 1.6, False)

Dim px, py
For Each px In Array(pcbX0 + 5, pcbX0 + 145)
    For Each py In Array(pcbY0 + 5, pcbY0 + 85)
        Call AddCylZ_MM(defPCB, px, py, pcbZ0 - 12, pcbZ0, 3.0, False)
        Call AddCylZ_MM(defPCB, px, py, pcbZ0 - 1, pcbZ0 + 3, 1.6, True)
    Next
Next

Call AddBoxMM(defPCB, pcbX0 + 61, pcbY0 + 16, pcbZ0 + 1.6, pcbX0 + 89, pcbY0 + 78, pcbZ0 + 14, False)
Call AddBoxMM(defPCB, pcbX0 + 18, pcbY0 + 24, pcbZ0 + 1.6, pcbX0 + 39, pcbY0 + 45, pcbZ0 + 11, False)
Call AddBoxMM(defPCB, pcbX0 + 18, pcbY0 + 52, pcbZ0 + 1.6, pcbX0 + 39, pcbY0 + 73, pcbZ0 + 11, False)
Call AddBoxMM(defPCB, pcbX0 + 2, pcbY0 + 18, pcbZ0 + 1.6, pcbX0 + 12, pcbY0 + 76, pcbZ0 + 12, False)
Call AddBoxMM(defPCB, pcbX0 + 14, pcbY0 + 3, pcbZ0 + 1.6, pcbX0 + 57, pcbY0 + 22, pcbZ0 + 13, False)
Call AddBoxMM(defPCB, pcbX0 + 93, pcbY0 + 3, pcbZ0 + 1.6, pcbX0 + 136, pcbY0 + 22, pcbZ0 + 13, False)
Call AddBoxMM(defPCB, pcbX0 + 69, pcbY0 + 2, pcbZ0 + 1.6, pcbX0 + 81, pcbY0 + 12, pcbZ0 + 12, False)
Call AddBoxMM(defPCB, pcbX0 + 118, pcbY0 + 22, pcbZ0 + 1.6, pcbX0 + 143, pcbY0 + 84, pcbZ0 + 12, False)
Call AddBoxMM(defPCB, pcbX0 + 20, pcbY0 + 96, pcbZ0 - 8, pcbX0 + 125, pcbY0 + 150, pcbZ0 + 18, False)

Call SetPartColorRGB(docPCB, 16, 185, 129)
Call docPCB.SaveAs(pathPCB, False)

' ============================================================================
' PART 4: CUM MAM XOAY BI SAT VUONG 71x71mm + SERVO MG996R 360 + CAM BIEN AS5600
' ============================================================================
WScript.Echo "[4/6] Dang ve Part 4: 04_Mam_Xoay_Bi_Sat_71x71_MG996R_360_AS5600.ipt ..."
Dim docTT, defTT, pathTT
pathTT = outDir & "\04_Mam_Xoay_Bi_Sat_71x71_MG996R_360_AS5600.ipt"
If fso.FileExists(pathTT) Then fso.DeleteFile(pathTT)
Set docTT = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
Set defTT = docTT.ComponentDefinition

Dim ttX, ttY, ttZ
ttX = 45 : ttY = 125 : ttZ = 175

Call AddBoxMM(defTT, ttX - 35.5, ttY - 35.5, ttZ, ttX + 35.5, ttY + 35.5, ttZ + 2.2, False)
Call AddCylZ_MM(defTT, ttX, ttY, ttZ + 2.2, ttZ + 5.8, 27.0, False)
Call AddBoxMM(defTT, ttX - 35.5, ttY - 35.5, ttZ + 5.8, ttX + 35.5, ttY + 35.5, ttZ + 8.0, False)

Dim sx, sy
For Each sx In Array(ttX - 26, ttX + 26)
    For Each sy In Array(ttY - 16, ttY + 16)
        Call AddCylZ_MM(defTT, sx, sy, ttZ - 38, ttZ, 2.5, False)
    Next
Next
Call AddBoxMM(defTT, ttX - 38, ttY - 18, ttZ - 14, ttX + 20, ttY + 18, ttZ - 11.5, False)
Call AddMG996RAt(defTT, ttX, ttY, ttZ - 39.5)

Call AddCylZ_MM(defTT, ttX, ttY, ttZ + 8.5, ttZ + 11.0, 4.0, False)
Call AddBoxMM(defTT, ttX - 11.5, ttY - 11.5, ttZ + 12.5, ttX + 11.5, ttY + 11.5, ttZ + 14.8, False)

Call SetPartColorRGB(docTT, 180, 198, 218)
Call docTT.SaveAs(pathTT, False)

' ============================================================================
' PART 5: CUM CANH TAY 3xSERVO MG996R 180° + KEP BANH RANG SONG SONG + ESP32-CAM
' ============================================================================
WScript.Echo "[5/6] Dang ve Part 5: 05_Canh_Tay_3xMG996R_180_Kep_Banh_Rang_ESP32CAM.ipt ..."
Dim docArm, defArm, pathArm
pathArm = outDir & "\05_Canh_Tay_3xMG996R_180_Kep_Banh_Rang_ESP32CAM.ipt"
If fso.FileExists(pathArm) Then fso.DeleteFile(pathArm)
Set docArm = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
Set defArm = docArm.ComponentDefinition

Dim ax, ay, az
ax = 45 : ay = 125 : az = 185

Call AddBoxMM(defArm, ax - 22, ay - 22, az, ax + 22, ay + 22, az + 3.0, False)
Call AddBoxMM(defArm, ax - 20, ay - 22, az + 3.0, ax + 20, ay - 19, az + 48, False)
Call AddBoxMM(defArm, ax - 20, ay + 19, az + 3.0, ax + 20, ay + 22, az + 48, False)
Call AddMG996RAt(defArm, ax, ay, az + 4)

Call AddBoxMM(defArm, ax - 12, ay - 18, az + 35, ax + 12, ay - 15, az + 145, False)
Call AddBoxMM(defArm, ax - 12, ay + 15, az + 35, ax + 12, ay + 18, az + 145, False)

Call AddMG996RAt(defArm, ax, ay, az + 115)
Call AddBoxMM(defArm, ax - 90, ay - 14, az + 145, ax + 10, ay - 11, az + 163, False)
Call AddBoxMM(defArm, ax - 90, ay + 11, az + 145, ax + 10, ay + 14, az + 163, False)

Dim gx
gx = ax - 90
Call AddMG996RAt(defArm, gx + 15, ay, az + 125)
Call AddBoxMM(defArm, gx - 12, ay - 38, az + 152, gx + 4, ay + 38, az + 160, False)
Call AddCylZ_MM(defArm, gx - 6, ay - 14, az + 160, az + 165, 13.0, False)
Call AddCylZ_MM(defArm, gx - 6, ay + 14, az + 160, az + 165, 13.0, False)
Call AddBoxMM(defArm, gx - 58, ay - 30, az + 148, gx - 12, ay - 24, az + 164, False)
Call AddBoxMM(defArm, gx - 58, ay + 24, az + 148, gx - 12, ay + 30, az + 164, False)

Call AddBoxMM(defArm, gx - 18, ay - 20, az + 165, gx - 12, ay + 20, az + 192, False)
Call AddCylZ_MM(defArm, gx - 20, ay, az + 174, az + 186, 6.5, False)

Call SetPartColorRGB(docArm, 239, 68, 68)
Call docArm.SaveAs(pathArm, False)

' ============================================================================
' PART 6: CAM BIEN YDLIDAR X2 (NOC TRAI CABIN) + SIEU AM HC-SR05 (CAN TRUOC)
' ============================================================================
WScript.Echo "[6/6] Dang ve Part 6: 06_Cam_Bien_YDLidar_X2_Va_HCSR05.ipt ..."
Dim docSen, defSen, pathSen
pathSen = outDir & "\06_Cam_Bien_YDLidar_X2_Va_HCSR05.ipt"
If fso.FileExists(pathSen) Then fso.DeleteFile(pathSen)
Set docSen = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
Set defSen = docSen.ComponentDefinition

Dim lx, ly
lx = 45 : ly = 45
Call AddCylZ_MM(defSen, lx - 16, ly - 16, 175, 205, 2.5, False)
Call AddCylZ_MM(defSen, lx + 16, ly - 16, 175, 205, 2.5, False)
Call AddCylZ_MM(defSen, lx - 16, ly + 16, 175, 205, 2.5, False)
Call AddCylZ_MM(defSen, lx + 16, ly + 16, 175, 205, 2.5, False)
Call AddCylZ_MM(defSen, lx, ly, 205, 223, 29.0, False)
Call AddCylZ_MM(defSen, lx, ly, 223, 239, 27.0, False)

Call AddBoxMM(defSen, -4, 102.5, 48, -1, 147.5, 68, False)
Call AddBoxMM(defSen, -14, 104, 50, -4, 120, 66, False)
Call AddBoxMM(defSen, -14, 130, 50, -4, 146, 66, False)

Call SetPartColorRGB(docSen, 59, 130, 246)
Call docSen.SaveAs(pathSen, False)

' ============================================================================
' TAO BAN VE LAP TONG THE TRONG INVENTOR (.IAM ASSEMBLY DOCUMENT)
' ============================================================================
WScript.Echo "[*] Dang ghep tat ca 6 Part vao Ban Ve Lap: AGV_Xe_Tai_Dau_Vuong_Assembly.iam ..."
Dim docAssy, defAssy, pathAssy, matId
pathAssy = outDir & "\AGV_Xe_Tai_Dau_Vuong_Assembly.iam"
If fso.FileExists(pathAssy) Then fso.DeleteFile(pathAssy)

Set docAssy = invApp.Documents.Add(kAssemblyDocumentObject, templateAssy, True)
Set defAssy = docAssy.ComponentDefinition
Set matId = tg.CreateMatrix()

Dim occ1, occ2, occ3, occ4, occ5, occ6
Set occ1 = defAssy.Occurrences.Add(pathFrame, matId)
occ1.Grounded = True
Set occ2 = defAssy.Occurrences.Add(pathWheels, matId)
Set occ3 = defAssy.Occurrences.Add(pathPCB, matId)
Set occ4 = defAssy.Occurrences.Add(pathTT, matId)
Set occ5 = defAssy.Occurrences.Add(pathArm, matId)
Set occ6 = defAssy.Occurrences.Add(pathSen, matId)

docFrame.Close(True)
docWheels.Close(True)
docPCB.Close(True)
docTT.Close(True)
docArm.Close(True)
docSen.Close(True)

docAssy.Activate()
On Error Resume Next
invApp.ActiveView.DisplayMode = kShadedWithEdgesRendering
invApp.ActiveView.GoHome()
invApp.ActiveView.Fit()
On Error GoTo 0

Call docAssy.SaveAs(pathAssy, False)
invApp.SilentOperation = False

WScript.Echo "============================================================================"
WScript.Echo " [HOAN TAT 100%] DA VE TRUC TIEP BAN VE LAP TRONG AUTODESK INVENTOR 2027!"
WScript.Echo " -> File Assembly (.IAM): " & pathAssy
WScript.Echo "============================================================================"
