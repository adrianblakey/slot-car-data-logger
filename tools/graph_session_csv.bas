' Copyright @ 2026 Adrian Blakey. All rights reserved
' graph_session_csv.bas — LibreOffice Calc Basic macro.
'
' Graphs a decoded session CSV (see tools/decode_log.py) that has been
' opened in Calc: column A = t_ms (time, X axis), columns B/C/D =
' current_A / track_V / supply_V (the three Y series). Column E (marker,
' 1 on a lap-marker row) isn't plotted as a value series — each marker
' instead draws as a black vertical line spanning the current_A axis, via
' helper data the macro writes to spare columns G:H. Skips over the
' leading "# key=value" metadata comment lines that decode_log.py writes
' before the real header row, by searching column A for the cell
' containing exactly "t_ms".
'
' Install:
'   1. Open the session CSV in LibreOffice Calc.
'   2. Tools > Macros > Edit Macros... (or Basic IDE).
'   3. In "My Macros" (or the document), insert a new Module and paste
'      this file's contents in.
'   4. With the CSV window focused, Tools > Macros > Run Macro... >
'      choose GraphSessionCSV, or just press F5 in the IDE.
'
' Re-running replaces any previously-created chart of the same name, so
' it's safe to run again after editing the sheet.

Sub GraphSessionCSV
    Dim oDoc As Object, oSheet As Object, oCharts As Object, oChart As Object
    Dim oDiagram As Object, oCursor As Object, oPosCell As Object
    Dim oRect As New com.sun.star.awt.Rectangle
    Dim oRangeAddr(0) As New com.sun.star.table.CellRangeAddress
    Dim headerRow As Integer, lastRow As Long
    Dim i As Integer
    Const CHART_NAME As String = "SessionChart"

    oDoc = ThisComponent
    oSheet = oDoc.CurrentController.ActiveSheet

    ' ── Find the real header row: column A cell whose text is "t_ms" ───────
    headerRow = -1
    For i = 0 To 200
        If oSheet.getCellByPosition(0, i).getString() = "t_ms" Then
            headerRow = i
            Exit For
        End If
    Next i
    If headerRow = -1 Then
        MsgBox "Couldn't find the header row (a cell in column A containing ""t_ms"")." & Chr(10) & _
               "Make sure a decoded session CSV is loaded, with its header row intact.", 48, "Graph Session CSV"
        Exit Sub
    End If

    ' ── Find the last data row below the header ─────────────────────────────
    oCursor = oSheet.createCursorByRange(oSheet.getCellByPosition(0, headerRow))
    oCursor.gotoEndOfUsedArea(False)
    lastRow = oCursor.RangeAddress.EndRow
    If lastRow <= headerRow Then
        MsgBox "No data rows found below the header row.", 48, "Graph Session CSV"
        Exit Sub
    End If

    ' ── Scan the data once for dynamic axis bounds ──────────────────────────
    ' current_A's real swing varies a lot session to session; a fixed axis
    ' makes a mild session look flat and clips a hard one. Round outward to
    ' the nearest whole unit instead — floor the real min, ceil the real
    ' max — so the axis always fully contains the data (e.g. a 12.4 V peak
    ' gets a 13 V ceiling, a -5.3 A trough gets a -6 A floor).
    ' getDataArray() coerces every cell to a Double; the blank current_A
    ' cells on lap-marker rows (see log_record.py's sentinel) come back as
    ' 0.0, which is harmless here since 0 A is always within the real range.
    ' Columns A:E this time (not just B:D) — t_ms and the marker flag are
    ' needed below to place the lap-marker lines.
    Dim vArr
    vArr = oSheet.getCellRangeByPosition(0, headerRow + 1, 4, lastRow).getDataArray()

    Dim curMin As Double, curMax As Double, voltMax As Double
    Dim vi As Long
    Dim v As Double

    curMin = vArr(0)(1)
    curMax = vArr(0)(1)
    voltMax = 0

    For vi = 0 To UBound(vArr)
        v = vArr(vi)(1)
        If v < curMin Then curMin = v
        If v > curMax Then curMax = v

        v = vArr(vi)(2)
        If v > voltMax Then voltMax = v

        v = vArr(vi)(3)
        If v > voltMax Then voltMax = v
    Next vi

    Dim axisCurMin As Double, axisCurMax As Double, axisVoltMax As Double
    axisCurMin = Int(curMin)      ' floor
    axisCurMax = -Int(-curMax)    ' ceil
    If axisCurMin = axisCurMax Then   ' degenerate: perfectly flat current
        axisCurMin = axisCurMin - 1
        axisCurMax = axisCurMax + 1
    End If
    axisVoltMax = -Int(-voltMax)  ' ceil
    If axisVoltMax < 1 Then axisVoltMax = 1   ' degenerate: no voltage recorded

    ' ── Lap-marker helper data ───────────────────────────────────────────
    ' A second pass over the same in-memory scan (needs axisCurMin/Max,
    ' only just computed above). Written to spare columns G:H, two rows per
    ' marker event — (t, axisCurMin) then (t, axisCurMax) — with a blank
    ' row after each to break the connecting line between separate events,
    ' so each marker draws as its own isolated vertical segment rather than
    ' one zigzag joining all of them. This becomes a 4th chart data series
    ' below, bound to its own X column since marker timestamps don't line
    ' up row-for-row with the main A:D data.
    Const MARKER_COL As Integer = 6   ' column G; H is COL+1
    Dim markerHdrRow As Long, markerDataStartRow As Long, markerOutRow As Long
    Dim markerCount As Long
    markerHdrRow = headerRow
    oSheet.getCellByPosition(MARKER_COL, markerHdrRow).setString("marker_t")
    oSheet.getCellByPosition(MARKER_COL + 1, markerHdrRow).setString("lap marker")
    markerDataStartRow = markerHdrRow + 1
    markerOutRow = markerDataStartRow
    markerCount = 0

    For vi = 0 To UBound(vArr)
        If vArr(vi)(4) = 1 Then
            oSheet.getCellByPosition(MARKER_COL, markerOutRow).setValue(vArr(vi)(0))
            oSheet.getCellByPosition(MARKER_COL + 1, markerOutRow).setValue(axisCurMin)
            markerOutRow = markerOutRow + 1
            oSheet.getCellByPosition(MARKER_COL, markerOutRow).setValue(vArr(vi)(0))
            oSheet.getCellByPosition(MARKER_COL + 1, markerOutRow).setValue(axisCurMax)
            markerOutRow = markerOutRow + 1
            markerOutRow = markerOutRow + 1   ' blank separator row, left empty
            markerCount = markerCount + 1
        End If
    Next vi

    ' ── Data range: columns A:D (t_ms, current_A, track_V, supply_V) ───────
    ' Column E (marker) is deliberately excluded.
    oRangeAddr(0).Sheet = oSheet.RangeAddress.Sheet
    oRangeAddr(0).StartColumn = 0
    oRangeAddr(0).StartRow = headerRow
    oRangeAddr(0).EndColumn = 3
    oRangeAddr(0).EndRow = lastRow

    oCharts = oSheet.Charts
    If oCharts.hasByName(CHART_NAME) Then
        oCharts.removeByName(CHART_NAME)
    End If

    ' Anchor the chart just right of column D/E, level with the header row,
    ' so it doesn't cover the data table.
    oPosCell = oSheet.getCellByPosition(5, headerRow)
    oRect.X = oPosCell.Position.X
    oRect.Y = oPosCell.Position.Y
    oRect.Width = 26000   ' 1/100 mm -> 26 cm
    oRect.Height = 14000  ' 14 cm

    ' bColumnHeaders=True: row "headerRow" supplies series names (current_A,
    ' track_V, supply_V). bRowHeaders=True: column A supplies X values once
    ' the diagram is switched to XYDiagram below.
    oCharts.addNewByName(CHART_NAME, oRect, oRangeAddr, True, True)

    oChart = oCharts.getByName(CHART_NAME).getEmbeddedObject()
    oChart.setDiagram(oChart.createInstance("com.sun.star.chart.XYDiagram"))

    ' Re-fetch fresh references AFTER the diagram swap. An oChart/oDiagram
    ' handle obtained before setDiagram() silently stops reflecting the
    ' live document once the diagram is replaced: property writes below
    ' land on a stale copy instead of raising an error. Confirmed by
    ' testing — HasMainTitle took effect but Title.String right after it
    ' silently didn't, and everything past that point (axis titles,
    ' legend) was affected too.
    oChart = oCharts.getByName(CHART_NAME).getEmbeddedObject()
    oDiagram = oChart.getDiagram()
    oDiagram.Lines = True

    oChart.HasMainTitle = True
    oChart.Title.String = SessionTitle(oDoc)

    oDiagram.HasXAxisTitle = True
    oDiagram.XAxisTitle.String = "t_ms"

    oChart.HasLegend = True

    ' ── Two Y axes: current (left/primary), volts (right/secondary) ────────
    ' Explicit ranges (computed above), not auto-scale, so the axis rounds
    ' to nice whole units rather than whatever LibreOffice's auto-scaler
    ' picks. Titles are set later, via chart2 — see the comment down there.
    Dim oYAxis As Object
    oYAxis = oDiagram.YAxis
    oYAxis.AutoMax = False
    oYAxis.AutoMin = False
    oYAxis.Max = axisCurMax
    oYAxis.Min = axisCurMin

    oDiagram.HasSecondaryYAxis = True
    Dim oYAxis2 As Object
    oYAxis2 = oDiagram.SecondaryYAxis
    oYAxis2.AutoMax = False
    oYAxis2.AutoMin = False
    oYAxis2.Max = axisVoltMax
    oYAxis2.Min = 0

    ' ── Per-series colour + axis assignment ─────────────────────────────────
    ' The legacy oDiagram.getDataRowProperties(i) object turned out to be a
    ' disconnected snapshot on this LibreOffice build: writes to .LineColor/
    ' .Axis on it don't raise an error but silently don't persist either
    ' (confirmed by immediate readback after setting). The chart2 API's
    ' data-series objects, reached via the diagram's coordinate system, do
    ' persist correctly (confirmed the same way) — use that instead.
    ' Row order matches the source columns B, C, D: current_A, track_V,
    ' supply_V. current_A stays on the primary (left) axis; the two voltage
    ' series move to the secondary (right) axis (AttachedAxisIndex 1).
    Dim oDiagram2 As Object
    Dim oCoordSystems, oCoordSys As Object
    Dim oChartTypes, oChartType As Object
    Dim oSeriesArr

    oDiagram2 = oChart.getFirstDiagram()
    oCoordSystems = oDiagram2.getCoordinateSystems()
    oCoordSys = oCoordSystems(0)
    oChartTypes = oCoordSys.getChartTypes()
    oChartType = oChartTypes(0)
    oSeriesArr = oChartType.getDataSeries()

    ' Color, not LineColor — for this chart geometry (XY scatter, Lines
    ' rendering) the actual stroke drawn on screen is taken from Color/
    ' FillColor, not from LineColor/LineProperties. Confirmed by reading
    ' both back: LineColor took the value written to it, but the rendered
    ' export kept LibreOffice's default theme colour until Color was set
    ' too. Also disable per-point symbols: with 3102 points a marker at
    ' every sample is visual noise and, worse, symbols default to their own
    ' un-set theme colour independent of Color, which is what actually made
    ' the first attempt look wrong at a glance.
    Dim oSym As New com.sun.star.chart2.Symbol
    oSym.Style = com.sun.star.chart2.SymbolStyle.NONE

    ' 1/100 mm. A hairline (10 = 0.10 mm) anti-aliases so much of each
    ' line's rendered pixels blend into the grey plot background that the
    ' colours read as washed out even though they're already pure RGB
    ' primaries (max saturation/value) — a bit wider gives more solid
    ' colour coverage per line without going thick.
    Const LINE_WIDTH_HMM As Long = 18

    oSeriesArr(0).Color = MakeColor(255, 255, 0)   ' current_A, yellow
    oSeriesArr(0).Symbol = oSym
    oSeriesArr(0).LineWidth = LINE_WIDTH_HMM

    oSeriesArr(1).Color = MakeColor(255, 0, 0)     ' track_V, red
    oSeriesArr(1).AttachedAxisIndex = 1
    oSeriesArr(1).Symbol = oSym
    oSeriesArr(1).LineWidth = LINE_WIDTH_HMM

    oSeriesArr(2).Color = MakeColor(0, 0, 255)     ' supply_V, blue
    oSeriesArr(2).AttachedAxisIndex = 1
    oSeriesArr(2).Symbol = oSym
    oSeriesArr(2).LineWidth = LINE_WIDTH_HMM

    ' ── Lap-marker vertical lines, as a 4th series ──────────────────────
    ' Bound to its own G:H range (built above) rather than reusing the
    ' A:D range's shared X column, since marker timestamps are a short,
    ' separate list, not row-aligned with the main data. A plain 4th
    ' column added to the original addNewByName range would have plotted
    ' each marker against whatever t_ms happened to share its row number —
    ' meaningless here — so this goes through the lower-level data-provider
    ' API instead to give the series its own independent X values.
    If markerCount > 0 Then
        Dim oDP As Object
        oDP = oChart.getDataProvider()

        Dim rMarkerX As Object, rMarkerY As Object, rMarkerLabel As Object
        rMarkerX = oSheet.getCellRangeByPosition(MARKER_COL, markerDataStartRow, MARKER_COL, markerOutRow - 2)
        rMarkerY = oSheet.getCellRangeByPosition(MARKER_COL + 1, markerDataStartRow, MARKER_COL + 1, markerOutRow - 2)
        rMarkerLabel = oSheet.getCellByPosition(MARKER_COL + 1, markerHdrRow)

        Dim seqMarkerX As Object, seqMarkerY As Object, seqMarkerLabel As Object
        seqMarkerX = oDP.createDataSequenceByRangeRepresentation(rMarkerX.AbsoluteName)
        seqMarkerY = oDP.createDataSequenceByRangeRepresentation(rMarkerY.AbsoluteName)
        seqMarkerLabel = oDP.createDataSequenceByRangeRepresentation(rMarkerLabel.AbsoluteName)
        seqMarkerX.Role = "values-x"
        seqMarkerY.Role = "values-y"

        Dim lsMarkerX As Object, lsMarkerY As Object
        lsMarkerX = createUnoService("com.sun.star.chart2.data.LabeledDataSequence")
        lsMarkerX.setValues(seqMarkerX)
        lsMarkerY = createUnoService("com.sun.star.chart2.data.LabeledDataSequence")
        lsMarkerY.setValues(seqMarkerY)
        lsMarkerY.setLabel(seqMarkerLabel)

        Dim oMarkerSeriesData(1) As Object
        oMarkerSeriesData(0) = lsMarkerX
        oMarkerSeriesData(1) = lsMarkerY

        Dim oMarkerSeries As Object
        oMarkerSeries = createUnoService("com.sun.star.chart2.DataSeries")
        oMarkerSeries.setData(oMarkerSeriesData())
        oMarkerSeries.Color = MakeColor(0, 0, 0)   ' black — distinct from the 3 trace colours
        oMarkerSeries.LineWidth = LINE_WIDTH_HMM
        oMarkerSeries.Symbol = oSym

        oChartType.addDataSeries(oMarkerSeries)
    End If

    ' ── Y axis titles, both built via chart2 ─────────────────────────────
    ' The legacy diagram has no HasSecondaryYAxisTitle/SecondaryYAxisTitle
    ' property pair (confirmed earlier — "method not found"), unlike the
    ' primary axis's ChartAxisYSupplier — so the secondary title has to go
    ' through the chart2 axis object's XTitled interface instead. The
    ' primary title *could* still use the legacy oDiagram.YAxisTitle, but
    ' that object is a different underlying type (no ReferencePageSize
    ' property at all) that scales its text independently of — and, at
    ' this chart's size, visibly smaller than — a chart2 Title at the same
    ' nominal CharHeight. Building both titles the same way here instead
    ' guarantees they render at the same size, rather than chasing a
    ' CharHeight number that isn't actually what drives the mismatch.
    Dim oAxisY1 As Object, oAxisY2 As Object
    oAxisY1 = oCoordSys.getAxisByDimension(1, 0)
    oAxisY2 = oCoordSys.getAxisByDimension(1, 1)

    Dim oTitle1 As Object, oTitle2 As Object
    Dim oFS1(0) As Object, oFS2(0) As Object

    oTitle1 = createUnoService("com.sun.star.chart2.Title")
    oFS1(0) = createUnoService("com.sun.star.chart2.FormattedString")
    oFS1(0).String = "track current"
    oTitle1.setText(oFS1())
    oTitle1.TextRotation = 90.0
    oAxisY1.setTitleObject(oTitle1)

    oTitle2 = createUnoService("com.sun.star.chart2.Title")
    oFS2(0) = createUnoService("com.sun.star.chart2.FormattedString")
    oFS2(0).String = "supply and track voltages"
    oTitle2.setText(oFS2())
    oTitle2.TextRotation = 90.0
    oAxisY2.setTitleObject(oTitle2)

    ' Force a full repaint. The colour/axis writes above go through the
    ' newer chart2 API on a chart originally built via the older chart1
    ' API (setDiagram(XYDiagram)) — the on-screen embedded OLE preview may
    ' not be listening for chart2-only property changes the way it does
    ' for chart1 ones, even though the underlying model is correct (a
    ' freshly-rendered export always reflects it). calculateAll() is a
    ' blunt but standard way to force everything, including embedded
    ' objects, to redraw from current state.
    ThisComponent.calculateAll()
End Sub

' Packs an RGB triple as the 0xRRGGBB Long the UNO chart API expects.
' Deliberately not using Basic's RGB() — on this LibreOffice build it's a
' VBA-compat function and VBA's RGB() packs bytes in the opposite (BGR)
' order, which silently produces the wrong on-screen colour rather than
' an error.
Function MakeColor(r As Integer, g As Integer, b As Integer) As Long
    MakeColor = r * 65536 + g * 256 + b
End Function

' Derives a chart title from the open document's filename, e.g.
' "session_20210101.csv — current / track_V / supply_V vs t_ms".
Function SessionTitle(oDoc As Object) As String
    Dim sUrl As String
    Dim aParts() As String
    sUrl = oDoc.getURL()
    aParts = Split(sUrl, "/")
    SessionTitle = aParts(UBound(aParts)) & " -- current_A / track_V / supply_V vs t_ms"
End Function
