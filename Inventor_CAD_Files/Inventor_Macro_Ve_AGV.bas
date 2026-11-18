Attribute VB_Name = "Module_Ve_AGV_3D"
' ============================================================================
' MACRO VBA CHAY TRUC TIEP BEN TRONG AUTODESK INVENTOR 2027 (ALT + F11 -> F5)
' ============================================================================
Option Explicit

Public Sub Ve_Toan_Bo_AGV_3D()
    Const kPartDocumentObject As Long = 12290
    Const kAssemblyDocumentObject As Long = 12291
    Const kPositiveExtentDirection As Long = 20993
    Const kJoinOperation As Long = 20481
    Const kCutOperation As Long = 20482
    Const kNewBodyOperation As Long = 20485
    Const kShadedWithEdgesRendering As Long = 8964

    Dim invApp As Object
    Set invApp = ThisApplication
    invApp.SilentOperation = True

    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    Dim outDir As String
    outDir = "E:\agv_server\Inventor_CAD_Files"
    If Not fso.FolderExists(outDir) Then
        fso.CreateFolder outDir
    End If

    Dim templatePart As String, templateAssy As String
    templatePart = invApp.FileManager.GetTemplateFile(kPartDocumentObject)
    templateAssy = invApp.FileManager.GetTemplateFile(kAssemblyDocumentObject)

    ' 1. PART 1: KHUNG SAT V LO CO 4 HOC RANH BANH XE
    Dim docFrame As Object, defFrame As Object, pathFrame As String
    pathFrame = outDir & "\01_Khung_Sat_V_Lo_Co_Hoc_Banh.ipt"
    If fso.FileExists(pathFrame) Then fso.DeleteFile pathFrame
    Set docFrame = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
    Set defFrame = docFrame.ComponentDefinition

    Call VBarX(defFrame, 0, 350, 45, 30, 25, 2#, True)
    Call VBarX(defFrame, 0, 350, 180, 30, 25, 2#, True)
    Call VBarY(defFrame, 0, 0, 250, 30, 25, 2#, True)
    Call VBarY(defFrame, 113, 0, 250, 30, 25, 2#, True)
    Call VBarY(defFrame, 212, 0, 250, 30, 25, 2#, True)
    Call VBarY(defFrame, 325, 0, 250, 30, 25, 2#, True)
    Call VBarX(defFrame, 113, 237, 0, 30, 25, 2#, False)
    Call VBarX(defFrame, 113, 237, 225, 30, 25, 2#, False)
    Call VBarY(defFrame, 120, 45, 205, 32, 20, 2#, False)
    Call VBarY(defFrame, 260, 45, 205, 32, 20, 2#, False)

    Call VBarX(defFrame, 0, 350, 0, 50, 25, 2#, True)
    Call VBarX(defFrame, 0, 350, 225, 50, 25, 2#, True)
    Call VBarY(defFrame, 0, 0, 250, 50, 25, 2#, False)
    Call VBarY(defFrame, 100, 0, 250, 50, 25, 2#, False)
    Call VBarY(defFrame, 325, 0, 250, 50, 25, 2#, False)

    Call VBarZ(defFrame, 0, 0, 75, 175, 25, 2#)
    Call VBarZ(defFrame, 0, 225, 75, 175, 25, 2#)
    Call VBarZ(defFrame, 75, 0, 75, 175, 25, 2#)
    Call VBarZ(defFrame, 75, 225, 75, 175, 25, 2#)

    Call VBarX(defFrame, 0, 100, 0, 150, 25, 2#, False)
    Call VBarX(defFrame, 0, 100, 225, 150, 25, 2#, False)
    Call VBarX(defFrame, 0, 100, 88, 150, 25, 2#, True)
    Call VBarX(defFrame, 0, 100, 137, 150, 25, 2#, True)
    Call VBarY(defFrame, 0, 0, 250, 150, 25, 2#, False)
    Call VBarY(defFrame, 75, 0, 250, 150, 25, 2#, False)

    Call VBarX(defFrame, 100, 350, 0, 100, 25, 2#, True)
    Call VBarX(defFrame, 100, 350, 225, 100, 25, 2#, True)
    Call VBarZ(defFrame, 325, 0, 75, 125, 25, 2#)
    Call VBarZ(defFrame, 325, 225, 75, 125, 25, 2#)
    Call VBarY(defFrame, 325, 0, 250, 100, 25, 2#, False)
    Call docFrame.SaveAs(pathFrame, False)

    ' 2. PART 2: 4 BANH MECANUM 80MM + 4 MOTOR XANH 1:90
    Dim docWheels As Object, defWheels As Object, pathWheels As String
    pathWheels = outDir & "\02_Cum_4_Banh_Mecanum80_Va_Motor_1_90.ipt"
    If fso.FileExists(pathWheels) Then fso.DeleteFile pathWheels
    Set docWheels = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
    Set defWheels = docWheels.ComponentDefinition
    Call AddWheelSub(defWheels, 65, 2, True)
    Call AddWheelSub(defWheels, 65, 248, False)
    Call AddWheelSub(defWheels, 285, 2, True)
    Call AddWheelSub(defWheels, 285, 248, False)
    Call docWheels.SaveAs(pathWheels, False)

    ' 3. PART 3: BO MACH PCB 150x90mm ALTIUM
    Dim docPCB As Object, defPCB As Object, pathPCB As String
    pathPCB = outDir & "\03_Bo_Mach_PCB_150x90_Altium.ipt"
    If fso.FileExists(pathPCB) Then fso.DeleteFile pathPCB
    Set docPCB = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
    Set defPCB = docPCB.ComponentDefinition
    Call BoxMM(defPCB, 125, 55, 44, 275, 145, 45.6, False)
    Call CylZ_MM(defPCB, 130, 60, 32, 44, 3#, False)
    Call CylZ_MM(defPCB, 270, 60, 32, 44, 3#, False)
    Call CylZ_MM(defPCB, 130, 140, 32, 44, 3#, False)
    Call CylZ_MM(defPCB, 270, 140, 32, 44, 3#, False)
    Call BoxMM(defPCB, 186, 71, 45.6, 214, 133, 58, False)
    Call BoxMM(defPCB, 143, 79, 45.6, 164, 100, 55, False)
    Call BoxMM(defPCB, 143, 107, 45.6, 164, 128, 55, False)
    Call BoxMM(defPCB, 139, 58, 45.6, 182, 77, 57, False)
    Call BoxMM(defPCB, 218, 58, 45.6, 261, 77, 57, False)
    Call BoxMM(defPCB, 243, 77, 45.6, 268, 139, 56, False)
    Call BoxMM(defPCB, 145, 151, 36, 250, 205, 62, False)
    Call docPCB.SaveAs(pathPCB, False)

    ' 4. PART 4: MAM XOAY BI SAT 71x71mm + MG996R 360 + AS5600
    Dim docTT As Object, defTT As Object, pathTT As String
    pathTT = outDir & "\04_Mam_Xoay_Bi_Sat_71x71_MG996R_360_AS5600.ipt"
    If fso.FileExists(pathTT) Then fso.DeleteFile pathTT
    Set docTT = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
    Set defTT = docTT.ComponentDefinition
    Call BoxMM(defTT, 9.5, 89.5, 175, 80.5, 160.5, 177.2, False)
    Call CylZ_MM(defTT, 45, 125, 177.2, 180.8, 27#, False)
    Call BoxMM(defTT, 9.5, 89.5, 180.8, 80.5, 160.5, 183, False)
    Call MG996R(defTT, 45, 125, 135.5)
    Call CylZ_MM(defTT, 45, 125, 183.5, 186, 4#, False)
    Call BoxMM(defTT, 33.5, 113.5, 187.5, 56.5, 136.5, 190, False)
    Call docTT.SaveAs(pathTT, False)

    ' 5. PART 5: CANH TAY 3xMG996R 180 + KEP BANH RANG + ESP32-CAM
    Dim docArm As Object, defArm As Object, pathArm As String
    pathArm = outDir & "\05_Canh_Tay_3xMG996R_180_Kep_Banh_Rang_ESP32CAM.ipt"
    If fso.FileExists(pathArm) Then fso.DeleteFile pathArm
    Set docArm = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
    Set defArm = docArm.ComponentDefinition
    Call BoxMM(defArm, 23, 103, 185, 67, 147, 188, False)
    Call MG996R(defArm, 45, 125, 189)
    Call BoxMM(defArm, 33, 107, 220, 57, 110, 330, False)
    Call BoxMM(defArm, 33, 140, 220, 57, 143, 330, False)
    Call MG996R(defArm, 45, 125, 300)
    Call BoxMM(defArm, -45, 111, 330, 55, 114, 348, False)
    Call BoxMM(defArm, -45, 136, 330, 55, 139, 348, False)
    Call MG996R(defArm, -30, 125, 310)
    Call BoxMM(defArm, -57, 87, 337, -41, 163, 345, False)
    Call BoxMM(defArm, -103, 95, 333, -57, 101, 349, False)
    Call BoxMM(defArm, -103, 149, 333, -57, 155, 349, False)
    Call BoxMM(defArm, -63, 105, 350, -57, 145, 377, False)
    Call docArm.SaveAs(pathArm, False)

    ' 6. PART 6: YDLIDAR X2 + HC-SR05
    Dim docSen As Object, defSen As Object, pathSen As String
    pathSen = outDir & "\06_Cam_Bien_YDLidar_X2_Va_HCSR05.ipt"
    If fso.FileExists(pathSen) Then fso.DeleteFile pathSen
    Set docSen = invApp.Documents.Add(kPartDocumentObject, templatePart, True)
    Set defSen = docSen.ComponentDefinition
    Call CylZ_MM(defSen, 45, 45, 175, 223, 29#, False)
    Call CylZ_MM(defSen, 45, 45, 223, 239, 27#, False)
    Call BoxMM(defSen, -4, 102.5, 48, -1, 147.5, 68, False)
    Call docSen.SaveAs(pathSen, False)

    ' 7. TAO BAN VE LAP TONG THE (.IAM)
    Dim docAssy As Object, defAssy As Object, pathAssy As String, matId As Object
    pathAssy = outDir & "\AGV_Xe_Tai_Dau_Vuong_Assembly.iam"
    If fso.FileExists(pathAssy) Then fso.DeleteFile pathAssy
    Set docAssy = invApp.Documents.Add(kAssemblyDocumentObject, templateAssy, True)
    Set defAssy = docAssy.ComponentDefinition
    Set matId = invApp.TransientGeometry.CreateMatrix()

    Call defAssy.Occurrences.Add(pathFrame, matId)
    Call defAssy.Occurrences.Add(pathWheels, matId)
    Call defAssy.Occurrences.Add(pathPCB, matId)
    Call defAssy.Occurrences.Add(pathTT, matId)
    Call defAssy.Occurrences.Add(pathArm, matId)
    Call defAssy.Occurrences.Add(pathSen, matId)

    docFrame.Close True
    docWheels.Close True
    docPCB.Close True
    docTT.Close True
    docArm.Close True
    docSen.Close True

    docAssy.Activate
    invApp.ActiveView.DisplayMode = kShadedWithEdgesRendering
    invApp.ActiveView.GoHome
    invApp.ActiveView.Fit
    Call docAssy.SaveAs(pathAssy, False)
    invApp.SilentOperation = False
    MsgBox "Da dung xong toan bo 6 Part (.IPT) va Ban Ve Lap (.IAM) tai: " & outDir, vbInformation, "Hoan Tat 100%"
End Sub

Private Sub BoxMM(compDef As Object, x1 As Double, y1 As Double, z1 As Double, x2 As Double, y2 As Double, z2 As Double, isCut As Boolean)
    On Error Resume Next
    Dim tg As Object: Set tg = ThisApplication.TransientGeometry
    Dim wp As Object: Set wp = compDef.WorkPlanes.AddByPlaneAndOffset(compDef.WorkPlanes.Item(3), z1 / 10#, False)
    wp.Visible = False
    Dim sk As Object: Set sk = compDef.Sketches.Add(wp)
    Call sk.SketchLines.AddAsTwoPointRectangle(tg.CreatePoint2d(x1 / 10#, y1 / 10#), tg.CreatePoint2d(x2 / 10#, y2 / 10#))
    Dim prof As Object: Set prof = sk.Profiles.AddForSolid()
    Dim dist As Double: dist = Abs(z2 - z1) / 10#
    If isCut Then
        Call compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, 20993, 20482)
    Else
        Err.Clear
        Call compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, 20993, 20481)
        If Err.Number <> 0 Then
            Err.Clear
            Call compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, 20993, 20485)
        End If
    End If
End Sub

Private Sub CylZ_MM(compDef As Object, cx As Double, cy As Double, z1 As Double, z2 As Double, r_mm As Double, isCut As Boolean)
    On Error Resume Next
    Dim tg As Object: Set tg = ThisApplication.TransientGeometry
    Dim wp As Object: Set wp = compDef.WorkPlanes.AddByPlaneAndOffset(compDef.WorkPlanes.Item(3), z1 / 10#, False)
    wp.Visible = False
    Dim sk As Object: Set sk = compDef.Sketches.Add(wp)
    Call sk.SketchCircles.AddByCenterRadius(tg.CreatePoint2d(cx / 10#, cy / 10#), r_mm / 10#)
    Dim prof As Object: Set prof = sk.Profiles.AddForSolid()
    Dim dist As Double: dist = Abs(z2 - z1) / 10#
    If isCut Then
        Call compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, 20993, 20482)
    Else
        Err.Clear
        Call compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, 20993, 20481)
        If Err.Number <> 0 Then
            Err.Clear
            Call compDef.Features.ExtrudeFeatures.AddByDistanceExtent(prof, dist, 20993, 20485)
        End If
    End If
End Sub

Private Sub VBarX(compDef As Object, x1 As Double, x2 As Double, y0 As Double, z0 As Double, vSize As Double, vThick As Double, punchHoles As Boolean)
    Call BoxMM(compDef, x1, y0, z0, x2, y0 + vSize, z0 + vThick, False)
    Call BoxMM(compDef, x1, y0, z0, x2, y0 + vThick, z0 + vSize, False)
    If punchHoles Then
        Dim hx As Double
        For hx = x1 + 15 To x2 - 15 Step 25
            Call CylZ_MM(compDef, hx, y0 + vSize * 0.55, z0 - 1, z0 + vThick + 1, 3.2, True)
        Next
    End If
End Sub

Private Sub VBarY(compDef As Object, x0 As Double, y1 As Double, y2 As Double, z0 As Double, vSize As Double, vThick As Double, punchHoles As Boolean)
    Call BoxMM(compDef, x0, y1, z0, x0 + vSize, y2, z0 + vThick, False)
    Call BoxMM(compDef, x0, y1, z0, x0 + vThick, y2, z0 + vSize, False)
End Sub

Private Sub VBarZ(compDef As Object, x0 As Double, y0 As Double, z1 As Double, z2 As Double, vSize As Double, vThick As Double)
    Call BoxMM(compDef, x0, y0, z1, x0 + vSize, y0 + vThick, z2, False)
    Call BoxMM(compDef, x0, y0, z1, x0 + vThick, y0 + vSize, z2, False)
End Sub

Private Sub MG996R(compDef As Object, cx As Double, cy As Double, zBase As Double)
    Call BoxMM(compDef, cx - 30.15, cy - 10#, zBase, cx + 10.15, cy + 10#, zBase + 36.6, False)
    Call BoxMM(compDef, cx - 36.8, cy - 9.75, zBase + 26.6, cx + 16.8, cy + 9.75, zBase + 29.1, False)
    Call CylZ_MM(compDef, cx, cy, zBase + 36.6, zBase + 47.6, 5#, False)
End Sub

Private Sub AddWheelSub(compDef As Object, wx As Double, wy As Double, isLeft As Boolean)
    If isLeft Then
        Call BoxMM(compDef, wx - 38, wy, 12, wx + 38, wy + 38, 68, False)
        Call BoxMM(compDef, wx - 28, wy, 2, wx + 28, wy + 38, 78, False)
        Call BoxMM(compDef, wx - 11.25, wy + 40, 30.6, wx + 11.25, wy + 95, 49.4, False)
    Else
        Call BoxMM(compDef, wx - 38, wy - 38, 12, wx + 38, wy, 68, False)
        Call BoxMM(compDef, wx - 28, wy - 38, 2, wx + 28, wy, 78, False)
        Call BoxMM(compDef, wx - 11.25, wy - 95, 30.6, wx + 11.25, wy - 40, 49.4, False)
    End If
End Sub
