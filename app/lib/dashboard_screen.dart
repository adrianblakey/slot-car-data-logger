// Copyright @ 2026 Adrian Blakey. All rights reserved
// dashboard_screen.dart — live status + controls for a connected logger.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import 'ble_protocol.dart';
import 'ble_service.dart';
import 'files_screen.dart';
import 'scan_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key, required this.ble});

  final BleService ble;

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  LoggerStatus? _status;
  SessionProfile? _profile;
  StreamSubscription<LoggerStatus>? _statusSub;
  StreamSubscription<BluetoothConnectionState>? _connSub;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _init();
    _connSub = widget.ble.connectionState.listen((state) {
      if (state == BluetoothConnectionState.disconnected) {
        _returnToScan();
      }
    });
  }

  Future<void> _init() async {
    try {
      final stream = await widget.ble.watchStatus();
      _statusSub = stream.listen((s) => setState(() => _status = s));
      final profile = await widget.ble.readProfile();
      setState(() => _profile = profile);
    } catch (e) {
      setState(() => _error = 'Failed to read device: $e');
    }
  }

  void _returnToScan() {
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => ScanScreen(ble: widget.ble)),
      (route) => false,
    );
  }

  @override
  void dispose() {
    _statusSub?.cancel();
    _connSub?.cancel();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action, {String? successMessage}) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
      if (successMessage != null && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(successMessage)));
      }
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _refreshProfile() async {
    final p = await widget.ble.readProfile();
    if (mounted) setState(() => _profile = p);
  }

  Future<void> _confirmErase() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Erase all data?'),
        content: const Text(
            'This deletes all recorded session files and logs on the device. This cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Erase', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (ok == true) {
      await _run(() => widget.ble.erase(), successMessage: 'Erased');
    }
  }

  Future<void> _pickLane() async {
    final lane = await showDialog<int>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('Set lane'),
        children: [
          for (var i = 1; i <= laneColors.length; i++)
            SimpleDialogOption(
              onPressed: () => Navigator.pop(context, i),
              child: Text('$i — ${laneColors[i - 1]}'),
            ),
        ],
      ),
    );
    if (lane != null) {
      await _run(() async {
        await widget.ble.laneSet(lane);
        await _refreshProfile();
      });
    }
  }

  Future<void> _editProfile() async {
    if (_profile == null) return;
    final trackCtrl = TextEditingController(text: _profile!.track);
    final controllerCtrl = TextEditingController(text: _profile!.controller);
    final carCtrl = TextEditingController(text: _profile!.car);
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit profile'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: trackCtrl, decoration: const InputDecoration(labelText: 'Track')),
            TextField(
                controller: controllerCtrl,
                decoration: const InputDecoration(labelText: 'Controller')),
            TextField(controller: carCtrl, decoration: const InputDecoration(labelText: 'Car')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Save')),
        ],
      ),
    );
    if (result == true) {
      await _run(() async {
        final p = await widget.ble.writeProfile({
          'track': trackCtrl.text,
          'controller': controllerCtrl.text,
          'car': carCtrl.text,
        });
        setState(() => _profile = p);
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _status;
    final profile = _profile;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.ble.device?.platformName ?? 'Logger'),
        actions: [
          IconButton(
            icon: const Icon(Icons.folder),
            tooltip: 'Files',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => FilesScreen(ble: widget.ble)),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.bluetooth_disabled),
            tooltip: 'Disconnect',
            onPressed: () async {
              await widget.ble.disconnect();
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          final s = await widget.ble.readStatus();
          await _refreshProfile();
          if (mounted) setState(() => _status = s);
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_error != null)
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                margin: const EdgeInsets.only(bottom: 12),
                color: Colors.red.shade100,
                child: Text(_error!, style: TextStyle(color: Colors.red.shade900)),
              ),
            if (_busy) const LinearProgressIndicator(),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: status == null
                    ? const Text('Reading status…')
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                status.recording ? Icons.fiber_manual_record : Icons.stop_circle,
                                color: status.recording ? Colors.red : Colors.grey,
                              ),
                              const SizedBox(width: 8),
                              Text(status.recording ? 'Recording' : 'Stopped',
                                  style: Theme.of(context).textTheme.titleMedium),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text('Records: ${status.recordCount}'),
                          Text('Flash free: ${status.flashFreePct}%'),
                          Row(
                            children: [
                              Icon(
                                status.wifiUp ? Icons.wifi : Icons.wifi_off,
                                size: 18,
                                color: status.wifiUp ? Colors.green : Colors.grey,
                              ),
                              const SizedBox(width: 4),
                              Text(status.wifiUp ? 'Wi-Fi up' : 'Wi-Fi down'),
                            ],
                          ),
                        ],
                      ),
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton.icon(
                  onPressed: _busy ? null : () => _run(() => widget.ble.start()),
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('Start'),
                ),
                FilledButton.icon(
                  onPressed: _busy ? null : () => _run(() => widget.ble.stop()),
                  icon: const Icon(Icons.stop),
                  label: const Text('Stop'),
                ),
                OutlinedButton.icon(
                  onPressed: _busy ? null : () => _run(() => widget.ble.mark(), successMessage: 'Marked'),
                  icon: const Icon(Icons.flag),
                  label: const Text('Mark'),
                ),
                OutlinedButton.icon(
                  onPressed: _busy ? null : _confirmErase,
                  icon: const Icon(Icons.delete_forever, color: Colors.red),
                  label: const Text('Erase'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text('Wi-Fi', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                OutlinedButton.icon(
                  onPressed: _busy
                      ? null
                      : () => _run(() => widget.ble.wifiStart(), successMessage: 'Wi-Fi start requested'),
                  icon: const Icon(Icons.wifi),
                  label: const Text('Start'),
                ),
                OutlinedButton.icon(
                  onPressed: _busy ? null : () => _run(() => widget.ble.wifiStop()),
                  icon: const Icon(Icons.wifi_off),
                  label: const Text('Stop'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text('Session profile', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: profile == null
                    ? const Text('Reading profile…')
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Track: ${profile.track}'),
                          Text('Race: ${profile.race}'),
                          Text('Lane: ${profile.lane} — ${laneColorName(profile.lane)}'),
                          Text('Controller: ${profile.controller}'),
                          Text('Car: ${profile.car}'),
                          const SizedBox(height: 12),
                          Wrap(
                            spacing: 8,
                            children: [
                              OutlinedButton(
                                onPressed: _busy
                                    ? null
                                    : () => _run(() async {
                                          await widget.ble.laneRotate();
                                          await _refreshProfile();
                                        }),
                                child: const Text('Rotate lane'),
                              ),
                              OutlinedButton(
                                onPressed: _busy ? null : _pickLane,
                                child: const Text('Set lane…'),
                              ),
                              OutlinedButton(
                                onPressed: _busy
                                    ? null
                                    : () => _run(() async {
                                          await widget.ble.raceToggle();
                                          await _refreshProfile();
                                        }),
                                child: const Text('Toggle race/practice'),
                              ),
                              OutlinedButton(
                                onPressed: _busy ? null : _editProfile,
                                child: const Text('Edit…'),
                              ),
                            ],
                          ),
                        ],
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
