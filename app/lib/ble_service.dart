// Copyright @ 2026 Adrian Blakey. All rights reserved
// ble_service.dart — thin wrapper around flutter_blue_plus implementing
// ble_protocol.dart's wire protocol. Mirrors tools/ble_cli.py's structure
// (connect/read/write helpers, then one function per BLE function) —
// that's the already-hardware-verified reference implementation of this
// same protocol; when in doubt about a sequencing/timing detail, that's
// what this was checked against.

import 'dart:async';
import 'dart:convert';

import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import 'ble_protocol.dart';

/// flutter_blue_plus requires declaring a use-case at connect time (see
/// BluetoothDevice.connect's `license` parameter). This is a personal/
/// hobby project, so License.nonprofit is the correct one — see that
/// enum's doc comment (and flutter_blue_plus's own LICENSE) before
/// changing this if this app is ever used commercially.
const License _fbpLicense = License.nonprofit;

class BleService {
  BluetoothDevice? _device;
  BluetoothCharacteristic? _statusChar;
  BluetoothCharacteristic? _controlChar;
  BluetoothCharacteristic? _profileChar;
  BluetoothCharacteristic? _fileSelectChar;
  BluetoothCharacteristic? _fileChunkChar;

  BluetoothDevice? get device => _device;
  bool get isConnected => _device != null;

  /// Scans for SCLogger-* devices. Caller cancels the subscription (e.g.
  /// via a Timer or when leaving the scan screen) — this doesn't stop the
  /// scan itself, call FlutterBluePlus.stopScan() for that.
  Future<void> startScan({Duration timeout = const Duration(seconds: 8)}) async {
    await FlutterBluePlus.startScan(
      withKeywords: [deviceNamePrefix],
      timeout: timeout,
    );
  }

  Stream<List<ScanResult>> get scanResults => FlutterBluePlus.scanResults;
  Stream<bool> get isScanning => FlutterBluePlus.isScanning;

  Future<void> stopScan() => FlutterBluePlus.stopScan();

  Future<void> connect(BluetoothDevice device) async {
    await device.connect(license: _fbpLicense);
    final services = await device.discoverServices();
    _statusChar = null;
    _controlChar = null;
    _profileChar = null;
    _fileSelectChar = null;
    _fileChunkChar = null;
    for (final service in services) {
      for (final char in service.characteristics) {
        final uuid = char.uuid.str128.toLowerCase();
        if (uuid == statusUuid) {
          _statusChar = char;
        } else if (uuid == controlUuid) {
          _controlChar = char;
        } else if (uuid == profileUuid) {
          _profileChar = char;
        } else if (uuid == fileSelectUuid) {
          _fileSelectChar = char;
        } else if (uuid == fileChunkUuid) {
          _fileChunkChar = char;
        }
      }
    }
    _device = device;
    final missing = <String>[
      if (_statusChar == null) 'status',
      if (_controlChar == null) 'control',
      if (_profileChar == null) 'profile',
      if (_fileSelectChar == null) 'file-select',
      if (_fileChunkChar == null) 'file-chunk',
    ];
    if (missing.isNotEmpty) {
      throw StateError(
          'Connected, but characteristic(s) not found: ${missing.join(", ")}. '
          'Wrong device, or ble_server.py protocol has changed.');
    }
  }

  Future<void> disconnect() async {
    await _device?.disconnect();
    _device = null;
  }

  Stream<BluetoothConnectionState> get connectionState {
    final d = _device;
    if (d == null) return const Stream.empty();
    return d.connectionState;
  }

  // ── Device Information ──────────────────────────────────────────────

  Future<Map<String, String>> readDeviceInfo() async {
    final services = await _device!.discoverServices();
    final values = <String, String>{};
    for (final service in services) {
      for (final char in service.characteristics) {
        final uuid = char.uuid.str128.toLowerCase();
        String? label;
        if (uuid == mfgUuid) label = 'Manufacturer';
        if (uuid == serUuid) label = 'Serial';
        if (uuid == fwRevUuid) label = 'Firmware';
        if (uuid == swRevUuid) label = 'Software';
        if (label != null) {
          values[label] = utf8.decode(await char.read());
        }
      }
    }
    return values;
  }

  // ── status ───────────────────────────────────────────────────────────

  Future<LoggerStatus> readStatus() async {
    final raw = await _statusChar!.read();
    return LoggerStatus.decode(raw);
  }

  /// Live status updates via BLE notify — main.py's status characteristic
  /// refreshes every 2s while connected (see ble_server.py's _status_task).
  Future<Stream<LoggerStatus>> watchStatus() async {
    await _statusChar!.setNotifyValue(true);
    return _statusChar!.lastValueStream
        .where((v) => v.isNotEmpty)
        .map(LoggerStatus.decode);
  }

  // ── control ──────────────────────────────────────────────────────────

  Future<void> writeControl(int cmd, [List<int> payload = const []]) async {
    await _controlChar!.write([cmd, ...payload], withoutResponse: false);
  }

  Future<void> start() => writeControl(cmdStart);
  Future<void> stop() => writeControl(cmdStop);
  Future<void> mark() => writeControl(cmdMark);
  Future<void> erase() => writeControl(cmdErase);
  Future<void> wifiStop() => writeControl(cmdWifiStop);
  Future<void> laneRotate() => writeControl(cmdLaneRotate);
  Future<void> raceToggle() => writeControl(cmdRaceToggle);
  Future<void> laneSet(int lane) => writeControl(cmdLaneSet, [lane]);

  /// Real Wi-Fi connection takes several seconds (confirmed ~6-8s on
  /// hardware) — poll rather than a single check, same reasoning as
  /// tools/ble_cli.py's cmd_wifi_start. Returns the final status; check
  /// .wifiUp to see whether it actually came up within [timeout].
  Future<LoggerStatus> wifiStart({Duration timeout = const Duration(seconds: 15)}) async {
    await writeControl(cmdWifiStart);
    final deadline = DateTime.now().add(timeout);
    LoggerStatus st = await readStatus();
    while (!st.wifiUp && DateTime.now().isBefore(deadline)) {
      await Future.delayed(const Duration(seconds: 1));
      st = await readStatus();
    }
    return st;
  }

  // ── profile ──────────────────────────────────────────────────────────

  Future<SessionProfile> readProfile() async {
    final raw = await _profileChar!.read();
    return SessionProfile.decode(raw);
  }

  Future<SessionProfile> writeProfile(Map<String, dynamic> updates) async {
    await _profileChar!.write(utf8.encode(jsonEncode(updates)), withoutResponse: false);
    // main.py's control-triggered profile mutations (lane-rotate etc.)
    // refresh_profile() immediately; a direct profile-characteristic write
    // like this one is handled synchronously by ble_server.py's
    // _profile_task, which writes the merged result straight back — no
    // notify-wait needed, just re-read.
    await Future.delayed(const Duration(milliseconds: 300));
    return readProfile();
  }

  // ── files ────────────────────────────────────────────────────────────

  /// Reads FILE_CHUNK, writes ctrlNext, repeats until a chunk comes back
  /// empty — whatever was most recently selected on FILE_SELECT (a real
  /// file, or the file listing itself). See ble_protocol.dart's
  /// chunkPacing doc comment for why the delay is required.
  Future<List<int>> _pullChunks({void Function(int bytesSoFar)? onProgress}) async {
    final data = <int>[];
    while (true) {
      final chunk = await _fileChunkChar!.read();
      if (chunk.isEmpty) break;
      data.addAll(chunk);
      onProgress?.call(data.length);
      await _fileSelectChar!.write([ctrlNext], withoutResponse: false);
      await Future.delayed(chunkPacing);
    }
    return data;
  }

  Future<List<FileEntry>> fetchFileList() async {
    await _fileSelectChar!.write([ctrlList], withoutResponse: false);
    await Future.delayed(chunkPacing);
    final raw = await _pullChunks();
    return FileEntry.decodeList(raw);
  }

  /// Downloads the file at [index] in the most recently fetched listing
  /// (fetchFileList's order — data files first, then logs, each sorted).
  /// An empty result on the very first read means the index is stale or
  /// out of range (the list changed since it was fetched); re-fetch it.
  Future<List<int>> downloadByIndex(int index, {void Function(int bytesSoFar)? onProgress}) async {
    await _fileSelectChar!.write(selectByIndexPayload(index), withoutResponse: false);
    await Future.delayed(chunkPacing);
    return _pullChunks(onProgress: onProgress);
  }
}
