// Copyright @ 2026 Adrian Blakey. All rights reserved
// files_screen.dart — list, download and share the device's data/log files.
//
// Phones have no meaningful "current directory" for a user to find a
// downloaded file in, so downloads go to the app's temp directory and are
// immediately handed to the OS share sheet (AirDrop, Files, email, etc.) —
// the user picks where it actually ends up.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import 'ble_protocol.dart';
import 'ble_service.dart';

class FilesScreen extends StatefulWidget {
  const FilesScreen({super.key, required this.ble});

  final BleService ble;

  @override
  State<FilesScreen> createState() => _FilesScreenState();
}

class _FilesScreenState extends State<FilesScreen> {
  List<FileEntry> _files = [];
  bool _loading = true;
  int? _downloadingIndex;
  int _downloadedBytes = 0;
  String? _error;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final files = await widget.ble.fetchFileList();
      setState(() => _files = files);
    } catch (e) {
      setState(() => _error = 'Failed to list files: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _download(int index, FileEntry entry) async {
    setState(() {
      _downloadingIndex = index;
      _downloadedBytes = 0;
      _error = null;
    });
    try {
      final bytes = await widget.ble.downloadByIndex(
        index,
        onProgress: (n) => setState(() => _downloadedBytes = n),
      );
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/${entry.name}');
      await file.writeAsBytes(bytes);
      if (!mounted) return;
      await SharePlus.instance.share(
        ShareParams(files: [XFile(file.path)], fileNameOverrides: [entry.name]),
      );
    } catch (e) {
      setState(() => _error = 'Download failed: $e');
    } finally {
      if (mounted) setState(() => _downloadingIndex = null);
    }
  }

  Future<void> _eraseAndRefresh() async {
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
    if (ok != true) return;
    try {
      await widget.ble.erase();
      await _refresh();
    } catch (e) {
      setState(() => _error = 'Erase failed: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Files'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loading ? null : _refresh),
          IconButton(
            icon: const Icon(Icons.delete_forever, color: Colors.red),
            tooltip: 'Erase all',
            onPressed: _files.isEmpty ? null : _eraseAndRefresh,
          ),
        ],
      ),
      body: Column(
        children: [
          if (_error != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              color: Colors.red.shade100,
              child: Text(_error!, style: TextStyle(color: Colors.red.shade900)),
            ),
          if (_loading) const LinearProgressIndicator(),
          Expanded(
            child: _files.isEmpty && !_loading
                ? const Center(child: Text('No files on device'))
                : ListView.builder(
                    itemCount: _files.length,
                    itemBuilder: (context, i) {
                      final f = _files[i];
                      final busy = _downloadingIndex == i;
                      return ListTile(
                        leading: Icon(f.kind == 'log' ? Icons.article : Icons.insert_chart),
                        title: Text(f.name),
                        subtitle: Text(busy
                            ? 'Downloading… $_downloadedBytes / ${f.size} bytes'
                            : '${f.kind} · ${f.size} bytes'),
                        trailing: busy
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : IconButton(
                                icon: const Icon(Icons.download),
                                onPressed: _downloadingIndex != null ? null : () => _download(i, f),
                              ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
