def wash_fork_and_put_in_bowl(robot_list):
    # robot_list = [robot2, robot3]
    # 0: SubTask 1: Wash the fork and put it in the bowl
    # 1: Go to the Fork using robot3.
    GoToObject(robot_list[1], 'Fork')
    # 2: Pick up the Fork using robot3.
    PickupObject(robot_list[1], 'Fork')
    # 3: Go to the Sink using robot3.
    GoToObject(robot_list[1], 'Sink')
    # 4: Put the fork inside the sink using robot3
    PutObject(robot_list[1], 'Fork', 'Sink')
    # 5: Switch on the Faucet to clean the Fork using robot2
    SwitchOn(robot_list[0], 'Faucet')
    # 6: Wait for a while to let the fork clean.
    time.sleep(5)
    # 7: Switch off the Faucet using robot2
    SwitchOff(robot_list[0], 'Faucet')
    # 8: Pick up the clean Fork using robot3.
    PickupObject(robot_list[1], 'Fork')
    # 9: Go to the Bowl using robot3.
    GoToObject(robot_list[1], 'Bowl')
    # 10: Place the Fork in the Bowl using robot3
    PutObject(robot_list[1], 'Fork', 'Bowl')

# Execute SubTask 1 with robot2 and robot3
wash_fork_and_put_in_bowl([robots[1], robots[2]])