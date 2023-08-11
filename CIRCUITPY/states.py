
from statemachine import StateMachine

STATES = [StateMachine.flash_start,
          StateMachine.calibrate,
          StateMachine.connect_to_wifi,
          StateMachine.input_track,
          StateMachine.connect_to_wifi_as_me,
          StateMachine.run_server]
