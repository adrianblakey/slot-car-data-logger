// Copyright @ 2026 Adrian Blakey. All rights reserved
// scan_screen.dart — find and connect to a SCLogger-* device.

import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:permission_handler/permission_handler.dart';

import 'ble_service.dart';
import 'dashboard_screen.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key, required this.ble});

  final BleService ble;

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  bool _connecting = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _requestPermissionsAndScan();
  }

  Future<void> _requestPermissionsAndScan() async {
    // Android 12+ needs runtime BLUETOOTH_SCAN/CONNECT; older Android needs
    // location. iOS's Info.plist usage string covers it there with no
    // runtime prompt through permission_handler.
    await [
      Permission.bluetoothScan,
      Permission.bluetoothConnect,
      Permission.locationWhenInUse,
    ].request();
    _startScan();
  }

  void _startScan() {
    setState(() => _error = null);
    widget.ble.startScan().catchError((e) {
      setState(() => _error = 'Scan failed: $e');
    });
  }

  Future<void> _connect(BluetoothDevice device) async {
    setState(() {
      _connecting = true;
      _error = null;
    });
    await widget.ble.stopScan();
    try {
      await widget.ble.connect(device);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => DashboardScreen(ble: widget.ble)),
      );
    } catch (e) {
      setState(() {
        _error = 'Connect failed: $e';
        _connecting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Slot Car Logger'),
        actions: [
          StreamBuilder<bool>(
            stream: widget.ble.isScanning,
            initialData: false,
            builder: (context, snap) {
              if (snap.data == true) {
                return const Padding(
                  padding: EdgeInsets.all(16),
                  child: SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                );
              }
              return IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: _startScan,
              );
            },
          ),
        ],
      ),
      body: Column(
        children: [
          if (_error != null)
            Container(
              width: double.infinity,
              color: Colors.red.shade100,
              padding: const EdgeInsets.all(12),
              child: Text(_error!, style: TextStyle(color: Colors.red.shade900)),
            ),
          if (_connecting) const LinearProgressIndicator(),
          Expanded(
            child: StreamBuilder<List<ScanResult>>(
              stream: widget.ble.scanResults,
              initialData: const [],
              builder: (context, snap) {
                final results = snap.data ?? const [];
                if (results.isEmpty) {
                  return const Center(child: Text('Looking for SCLogger-* devices…'));
                }
                return ListView.builder(
                  itemCount: results.length,
                  itemBuilder: (context, i) {
                    final r = results[i];
                    final name = r.advertisementData.advName.isNotEmpty
                        ? r.advertisementData.advName
                        : r.device.platformName;
                    return ListTile(
                      leading: const Icon(Icons.memory),
                      title: Text(name.isEmpty ? '(unnamed)' : name),
                      subtitle: Text('${r.device.remoteId} · RSSI ${r.rssi}'),
                      trailing: const Icon(Icons.chevron_right),
                      enabled: !_connecting,
                      onTap: () => _connect(r.device),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
