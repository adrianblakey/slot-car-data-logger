async def monitor_push_button(calibration_setting, board_flash_sequence, controller_flash_sequence):
    """Monitor the push button: each press changes the state.
    TODO: run the associated calibration"""
    with digitalio.DigitalInOut(board.GP22) as button:
        button.direction = digitalio.Direction.INPUT
        while True:
            if not button.value:
                print("Button pressed, this mode " + str(calibration_setting))
                calibration_setting.bump_mode()
                print("New mode " + str(calibration_setting))
                if calibration_setting.is_current():
                    board_flash_sequence.flashes = FlashSequence.C_FLASH
                    board_flash_sequence.separator = FlashSequence.SEPARATOR_FLASH
                elif calibration_setting.is_voltage():
                    board_flash_sequence.flashes = FlashSequence.V_FLASH
                    board_flash_sequence.separator = FlashSequence.SEPARATOR_FLASH
                else:
                    board_flash_sequence.flashes = FlashSequence.SOLID_ON
                    board_flash_sequence.separator = None

                # TODO if we enter current mode - remind the user to disconnect black and
                # TODO when they are ready hit the button again to run the calibration. Then
                # TODO replace the lead and hit button again to indicate end of calibration.
                # TODO maybe have some quick presses to just exit the calibration mode? x
            await asyncio.sleep(1)      # keep your finger on it for a second to change state

