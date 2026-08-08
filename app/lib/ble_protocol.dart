// Copyright @ 2026 Adrian Blakey. All rights reserved
// ble_protocol.dart — the wire protocol pico/src/ble_server.py exposes:
// UUIDs, control command bytes, and the (de)serialization for each
// characteristic's payload.
//
// Copied from pico/src/ble_server.py (and tools/ble_cli.py, the host CLI
// that already implements this same protocol) rather than shared/imported
// — this runs on a phone, that runs on the Pico under MicroPython. Keep
// all three in sync by hand if the protocol changes. See the README's "BLE
// control characteristic" and "BLE file transfer" sections for the full
// writeup of *why* the protocol looks like this — several of these choices
// (index-based file selection, chunked listing, the pacing delay) exist
// specifically because of bugs found on real hardware, not by design taste.

import 'dart:convert';
import 'dart:typed_data';

const String deviceNamePrefix = 'SCLogger-';

// Device Information service (standard).
const String fwRevUuid = '00002a26-0000-1000-8000-00805f9b34fb';
const String mfgUuid = '00002a29-0000-1000-8000-00805f9b34fb';
const String serUuid = '00002a25-0000-1000-8000-00805f9b34fb';
const String swRevUuid = '00002a28-0000-1000-8000-00805f9b34fb';

// Logger service (custom).
const String statusUuid = 'b1190efb-176f-4b32-a715-89b3425a4076';
const String controlUuid = 'b1190efc-176f-4b32-a715-89b3425a4076';
const String profileUuid = 'b1190efd-176f-4b32-a715-89b3425a4076';

// Files service (custom).
const String fileSelectUuid = 'b1190f02-176f-4b32-a715-89b3425a4076';
const String fileChunkUuid = 'b1190f03-176f-4b32-a715-89b3425a4076';

// Control command bytes. Most are a single byte; cmdLaneSet takes a second
// payload byte (1-based lane number, 1-8).
const int cmdStop = 0;
const int cmdStart = 1;
const int cmdMark = 2;
const int cmdErase = 3; // refused while recording; clears data AND old logs
const int cmdWifiStart = 4; // gated by a free-heap check on the device
const int cmdWifiStop = 5;
const int cmdLaneRotate = 6;
const int cmdLaneSet = 7;
const int cmdRaceToggle = 8;

// FILE_SELECT payloads — see ble_server.py's Files service comment for why
// selection is by index into the listing rather than by filename (real
// filenames don't reliably fit a single BLE write).
const int ctrlNext = 0x00;
const int ctrlList = 0x01;
const int ctrlSelect = 0x02;

// Minimum delay between writing "advance" and reading the next chunk.
// Confirmed on hardware: no delay intermittently produces a torn read (not
// a dropped chunk, but content from a different point in the file spliced
// into another chunk). 150ms confirmed clean — see README "found and fixed
// on hardware" #15.
const Duration chunkPacing = Duration(milliseconds: 150);

const List<String> profileFields = ['track', 'race', 'lane', 'controller', 'car'];

// Conventional slot car lane colours, index = lane number - 1. Mirrors
// pico/src/session_profile.py's LANE_COLORS.
const List<String> laneColors = [
  'Black', 'Purple', 'Yellow', 'Blue', 'Orange', 'Green', 'White', 'Red',
];

String laneColorName(int lane) =>
    (lane >= 1 && lane <= laneColors.length) ? laneColors[lane - 1] : '?';

class LoggerStatus {
  final bool recording;
  final int flashFreePct;
  final int recordCount;
  final bool wifiUp;

  const LoggerStatus({
    required this.recording,
    required this.flashFreePct,
    required this.recordCount,
    required this.wifiUp,
  });

  /// struct '<BBHB': recording(u8), flash_free_pct(u8), record_count(u16
  /// little-endian, wraps), wifi_up(u8). Matches ble_server.py's
  /// _STATUS_FMT exactly.
  factory LoggerStatus.decode(List<int> raw) {
    final bytes = Uint8List.fromList(raw);
    if (bytes.length < 5) {
      throw FormatException('status payload too short: ${bytes.length} bytes');
    }
    final bd = ByteData.sublistView(bytes);
    return LoggerStatus(
      recording: bd.getUint8(0) != 0,
      flashFreePct: bd.getUint8(1),
      recordCount: bd.getUint16(2, Endian.little),
      wifiUp: bd.getUint8(4) != 0,
    );
  }
}

class SessionProfile {
  final String track;
  final String race;
  final int lane;
  final String controller;
  final String car;

  const SessionProfile({
    required this.track,
    required this.race,
    required this.lane,
    required this.controller,
    required this.car,
  });

  factory SessionProfile.fromJson(Map<String, dynamic> j) => SessionProfile(
        track: j['track'] as String? ?? 'unknown',
        race: j['race'] as String? ?? 'practice',
        lane: (j['lane'] as num?)?.toInt() ?? 1,
        controller: j['controller'] as String? ?? 'unknown',
        car: j['car'] as String? ?? 'unknown',
      );

  factory SessionProfile.decode(List<int> raw) =>
      SessionProfile.fromJson(jsonDecode(utf8.decode(raw)) as Map<String, dynamic>);
}

class FileEntry {
  final String name;
  final String kind; // 'data' | 'log'
  final int size;

  const FileEntry({required this.name, required this.kind, required this.size});

  factory FileEntry.fromJson(Map<String, dynamic> j) => FileEntry(
        name: j['name'] as String,
        kind: j['kind'] as String,
        size: (j['size'] as num).toInt(),
      );

  /// Decodes the reassembled bytes from the FILE_SELECT ctrlList / chunked
  /// FILE_CHUNK protocol. Empty input (nothing on the device) is a valid,
  /// empty listing, not an error.
  static List<FileEntry> decodeList(List<int> raw) {
    if (raw.isEmpty) return const [];
    final decoded = jsonDecode(utf8.decode(raw)) as List;
    return decoded
        .map((e) => FileEntry.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}

/// The 3-byte FILE_SELECT payload to select a file by its position in the
/// most recently fetched listing (see ble_server.py: u16 little-endian).
List<int> selectByIndexPayload(int index) =>
    [ctrlSelect, index & 0xFF, (index >> 8) & 0xFF];
