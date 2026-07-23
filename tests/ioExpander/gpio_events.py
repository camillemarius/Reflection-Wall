
"""
gpio_events.py

Event-Manager für PCF8575

Unterstützt:
    - change events
    - rising edge
    - falling edge

Benötigt:
    PCF8575 mit register_callback()
"""


from pcf8575 import INPUT_MASK



class GPIOEventManager:


    def __init__(
        self,
        pcf
    ):

        self.pcf = pcf


        self._change_callbacks = {}
        self._rising_callbacks = {}
        self._falling_callbacks = {}


        self._last_state = (
            pcf.read_port()
        )


        #
        # Beim PCF8575 Interrupt anmelden
        #

        self.pcf.register_callback(
            self._event_handler
        )



    # -------------------------------------------------
    # Callback Registrierung
    # -------------------------------------------------

    def on_change(
        self,
        pin,
        callback
    ):
        """
        Callback bei jeder Änderung
        """

        self._check_input_pin(pin)


        self._change_callbacks[pin] = callback



    def on_rising(
        self,
        pin,
        callback
    ):
        """
        Callback bei LOW -> HIGH
        """

        self._check_input_pin(pin)


        self._rising_callbacks[pin] = callback



    def on_falling(
        self,
        pin,
        callback
    ):
        """
        Callback bei HIGH -> LOW
        """

        self._check_input_pin(pin)


        self._falling_callbacks[pin] = callback



    # -------------------------------------------------
    # Interrupt Verarbeitung
    # -------------------------------------------------

    def _event_handler(
        self,
        changed,
        new_state,
        old_state
    ):


        for pin in range(16):


            mask = (
                1 << pin
            )


            #
            # Nur geänderte Inputs
            #

            if not (changed & mask):

                continue



            old = (
                old_state >> pin
            ) & 1


            new = (
                new_state >> pin
            ) & 1



            #
            # Change Event
            #

            if pin in self._change_callbacks:

                self._change_callbacks[pin](
                    pin,
                    new
                )



            #
            # Rising
            #

            if old == 0 and new == 1:

                if pin in self._rising_callbacks:

                    self._rising_callbacks[pin](
                        pin
                    )



            #
            # Falling
            #

            if old == 1 and new == 0:

                if pin in self._falling_callbacks:

                    self._falling_callbacks[pin](
                        pin
                    )



        self._last_state = new_state



    # -------------------------------------------------
    # Hilfsfunktionen
    # -------------------------------------------------

    def _check_input_pin(
        self,
        pin
    ):


        if not (
            INPUT_MASK &
            (1 << pin)
        ):

            raise ValueError(
                f"P{pin:02d} ist kein Eingang"
            )