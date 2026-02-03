def wash_fork_and_put_in_bowl():
    # 0: SubTask 1: Wash the fork and put it in the bowl
    # 1: Go to the Fork.
    GoToObject('Fork')
    # 2: Pick up the Fork.
    PickupObject('Fork')
    # 3: Go to the Sink.
    GoToObject('Sink')
    # 4: Put the fork inside the sink
    PutObject('Fork', 'Sink')
    # 5: Switch on the Faucet to clean the Fork
    SwitchOn('Faucet')
    # 6: Wait for a while to let the fork clean.
    time.sleep(5)
    # 7: Switch off the Faucet
    SwitchOff('Faucet')
    # 8: Pick up the clean Fork.
    PickupObject('Fork')
    # 9: Go to the Bowl.
    GoToObject('Bowl')
    # 10: Place the Fork in the Bowl
    PutObject('Fork', 'Bowl')

# Execute SubTask 1
wash_fork_and_put_in_bowl()

# Task wash the fork and put it in the bowl is done