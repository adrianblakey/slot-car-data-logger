// Copyright @ 2026 Adrian Blakey. All rights reserved
// main.dart — entry point for the slot car logger BLE client.

import 'package:flutter/material.dart';

import 'ble_service.dart';
import 'scan_screen.dart';

void main() {
  runApp(const SlotCarBleApp());
}

class SlotCarBleApp extends StatelessWidget {
  const SlotCarBleApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Slot Car Logger',
      theme: ThemeData(colorSchemeSeed: Colors.deepOrange, useMaterial3: true),
      darkTheme: ThemeData(
        colorSchemeSeed: Colors.deepOrange,
        brightness: Brightness.dark,
        useMaterial3: true,
      ),
      home: ScanScreen(ble: BleService()),
    );
  }
}
