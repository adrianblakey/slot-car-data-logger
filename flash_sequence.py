class FlashSequence:
    """
    Encoding led flashes to give more meaningful errors.
    Class to hold a flash sequence
    Hold this as an array of on time/off time tuples and a separator to the next flash.
    """

    # Morse durations
    DI = .2  # 200msec shortest duration eye can see led on?
    DAH = 3 * DI
    SEP = 3 * DI

    QUICK_FLASHES = [(DI, DI)]  # on 200mSec, off 200mSec
    SOLID_ON = [(1, 0)]  # on, not off
    H_FLASH = [(DI, DI), (DI, DI), (DI, DI), (DI, DI)]
    C_FLASH = [(DAH, DI), (DI, DI), (DAH, DI), (DI, DI)]
    V_FLASH = [(DI, DI), (DI, DI), (DI, DI), (DAH, DI)]
    SEPARATOR_FLASH = [(0, DI + DI + DI)]     # off, not on for 3
    START_UP_QUICK_FLASH = [(DI, 0)]       # quick flash then off

    def __init__(self):
        self.flashes = FlashSequence.SOLID_ON
        self.separator = None

    def __str__(self) -> str:
        # TODO make this more useful
        for flashes in self._flashes:
            print(flashes[0], flashes[1])
        if self._separator is not None:
            for sep_flashes in self._separator:
                print(sep_flashes[0], sep_flashes[1])
        else:
            print("No separator between flashes")

    @property
    def flashes(self) -> [()]:
        return self._flashes

    @flashes.setter
    def flashes(self, flash_sequence: [(int, int)]):
        print("flashes setter")
        self._flashes = flash_sequence
        if np.all(np.equal(self._flashes, FlashSequence.QUICK_FLASHES)):
            print("setting quick flashes")
            self._separator = None
        elif np.all(np.equal(self._flashes, FlashSequence.SOLID_ON)):
            print("setting solid on")
            self._separator = None
        else:
            self._separator = FlashSequence.SEPARATOR_FLASH

    @property
    def separator(self) -> [()]:
        return self._separator

    @separator.setter
    def separator(self, value: [()]):
        self._separator = value


async def flash_led(pin, flash_sequence: [()]):
    """
        Flash a led according to the sequence
        TODO the board led high on low off - controller led is opposite
    """

    with digitalio.DigitalInOut(pin) as led:
        print("flash led")
        led.switch_to_output()
        if led.value:                            # Turn off the led for 100mS
            led.value = not led.value
        while True:
            print("flash the seqn ", flash_sequence)
            for flashes in flash_sequence.flashes:   # iterate through the on off tuples
                on_time = flashes[0]
                off_time = flashes[1]
                print("On time: ", str(on_time), " Off time: ", str(off_time))
                led.value = True  # turn on
                await asyncio.sleep(on_time)
                led.value = not led.value  # turn off
                await asyncio.sleep(off_time)   # wait off time
            if flash_sequence.separator is not None:
                print("flash seq separator", flash_sequence.separator)
                for flashes_sep in flash_sequence.separator:
                    on_time = flashes_sep[0]
                    off_time = flashes_sep[1]
                    print("Sep On time: ", str(on_time), " Sep Off time ", str(off_time))
                    if on_time != 0:
                        led.value = True  # turn on
                        await asyncio.sleep(on_time)
                    led.value = False  # turn off
                    await asyncio.sleep(off_time)  # wait off time

