import 'package:flutter_test/flutter_test.dart';

import 'package:slot_car_ble/main.dart';

void main() {
  testWidgets('App builds and shows the scan screen', (WidgetTester tester) async {
    await tester.pumpWidget(const SlotCarBleApp());
    expect(find.text('Slot Car Logger'), findsOneWidget);
  });
}
