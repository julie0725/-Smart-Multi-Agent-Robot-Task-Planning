import copy
import glob
import json
import os
import argparse
from pathlib import Path
from datetime import datetime
import random
import subprocess

import openai
import ai2thor.controller

import sys
sys.path.append(".")

import resources.actions as actions
import resources.robots as robots


def LM(prompt, gpt_version, max_tokens=128, temperature=0, stop=None, logprobs=1, frequency_penalty=0):
    
    if "gpt" not in gpt_version:
        response = openai.Completion.create(model=gpt_version, 
                                            prompt=prompt, 
                                            max_tokens=max_tokens, 
                                            temperature=temperature, 
                                            stop=stop, 
                                            logprobs=logprobs, 
                                            frequency_penalty = frequency_penalty)
        
        return response, response["choices"][0]["text"].strip()
    
    else:
        response = openai.ChatCompletion.create(model=gpt_version, 
                                            messages=prompt, 
                                            max_tokens=max_tokens, 
                                            temperature=temperature, 
                                            frequency_penalty = frequency_penalty)
        
        return response, response["choices"][0]["message"]["content"].strip()

def set_api_key(openai_api_key):
    # .txt 확장자가 있으면 그대로, 없으면 추가
    if openai_api_key.endswith('.txt'):
        key_file = Path(openai_api_key)
    else:
        key_file = Path(openai_api_key + '.txt')
    
    # 파일 읽고 공백/개행 제거
    openai.api_key = key_file.read_text().strip()
    print(f"API 키 로드됨: {openai.api_key[:10]}...")

# Function returns object list with name and properties.
def convert_to_dict_objprop(objs, obj_mass):
    objs_dict = []
    for i, obj in enumerate(objs):
        obj_dict = {'name': obj , 'mass' : obj_mass[i]}
        # obj_dict = {'name': obj , 'mass' : 1.0}
        objs_dict.append(obj_dict)
    return objs_dict

def get_ai2_thor_objects(floor_plan_id):
    # connector to ai2thor to get object list
    controller = ai2thor.controller.Controller(scene="FloorPlan"+str(floor_plan_id))
    obj = list([obj["objectType"] for obj in controller.last_event.metadata["objects"]])
    obj_mass = list([obj["mass"] for obj in controller.last_event.metadata["objects"]])
    controller.stop()
    obj = convert_to_dict_objprop(obj, obj_mass)
    return obj

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--floor-plan", type=int, required=True)
    parser.add_argument("--openai-api-key-file", type=str, default="api_key")
    parser.add_argument("--gpt-version", type=str, default="gpt-4", 
                        choices=['gpt-3.5-turbo', 'gpt-4', 'gpt-3.5-turbo-16k'])
    
    parser.add_argument("--prompt-decompse-set", type=str, default="train_task_decompose", 
                        choices=['train_task_decompose'])
    
    parser.add_argument("--prompt-allocation-set", type=str, default="train_task_allocation", 
                        choices=['train_task_allocation'])
    
    parser.add_argument("--test-set", type=str, default="final_test",
                        choices=['final_test'])

    parser.add_argument("--task-index", type=int, default=None,
                        help="Process only specific task index (0-based)")

    parser.add_argument("--log-results", type=bool, default=True)

    args = parser.parse_args()

    set_api_key(args.openai_api_key_file)
    
    if not os.path.isdir(f"./logs/"):
        os.makedirs(f"./logs/")
        
    # read the tasks        
    test_tasks = []
    robots_test_tasks = []  
    gt_test_tasks = []    
    trans_cnt_tasks = []
    max_trans_cnt_tasks = []  
    with open (f"./data/{args.test_set}/FloorPlan{args.floor_plan}.json", "r") as f:
        for line in f.readlines():
            test_tasks.append(list(json.loads(line).values())[0])
            robots_test_tasks.append(list(json.loads(line).values())[1])
            gt_test_tasks.append(list(json.loads(line).values())[2])
            trans_cnt_tasks.append(list(json.loads(line).values())[3])
            max_trans_cnt_tasks.append(list(json.loads(line).values())[4])
                    
    # Filter by task index if specified
    if args.task_index is not None:
        if args.task_index < 0 or args.task_index >= len(test_tasks):
            print(f"Error: task-index {args.task_index} out of range (0-{len(test_tasks)-1})")
            exit(1)

        # Keep only the specified task
        test_tasks = [test_tasks[args.task_index]]
        robots_test_tasks = [robots_test_tasks[args.task_index]]
        gt_test_tasks = [gt_test_tasks[args.task_index]]
        trans_cnt_tasks = [trans_cnt_tasks[args.task_index]]
        max_trans_cnt_tasks = [max_trans_cnt_tasks[args.task_index]]
        print(f"\n----Filtered to task index {args.task_index}----")

    print(f"\n----Test set tasks----\n{test_tasks}\nTotal: {len(test_tasks)} tasks\n")
    # prepare list of robots for the tasks
    available_robots = []
    for robots_list in robots_test_tasks:
        task_robots = []
        for i, r_id in enumerate(robots_list):
            rob = robots.robots [r_id-1]
            # rename the robot
            rob['name'] = 'robot' + str(i+1)
            task_robots.append(rob)
        available_robots.append(task_robots)
        
    
    ######## Train Task Decomposition ########
        
    # prepare train decompostion demonstration for ai2thor samples
    prompt = f"from skills import " + actions.ai2thor_actions
    prompt += f"\nimport time"
    prompt += f"\nimport threading"
    objects_ai = f"\n\nobjects = {get_ai2_thor_objects(args.floor_plan)}"
    prompt += objects_ai
    
    # read input train prompts
    decompose_prompt_file = open(os.getcwd() + "/data/pythonic_plans/" + args.prompt_decompse_set + ".py", "r")
    decompose_prompt = decompose_prompt_file.read()
    decompose_prompt_file.close()
    
    prompt += "\n\n" + decompose_prompt
    
    print ("Generating Decompsed Plans...")
    
    decomposed_plan = []
    for task in test_tasks:
        curr_prompt =  f"{prompt}\n\n# Task Description: {task}"
        
        if "gpt" not in args.gpt_version:
            # older gpt versions
            _, text = LM(curr_prompt, args.gpt_version, max_tokens=1000, stop=["def"], frequency_penalty=0.15)
        else:
            messages = [
                {"role": "system", "content": """You are a task decomposition expert for robot planning.

            CRITICAL OUTPUT FORMAT RULES:
            1. Output MUST be raw Python code only
            2. NEVER use markdown code blocks (```python or ```)
            3. Start directly with # GENERAL TASK DECOMPOSITION or def
            4. Output ONLY executable Python code
            5. NO text before or after the code

            CRITICAL TASK DECOMPOSITION RULES:
            1. SLICING OBJECTS REQUIRES A KNIFE:
               - Before any SliceObject() call, you MUST first:
                 a) GoToObject('Knife')
                 b) PickupObject('Knife')
               - After slicing, put the Knife down on a surface
               - Example: To slice tomato → Get Knife → Slice Tomato → Put Knife down

            2. Follow the examples provided exactly for similar tasks

            Generate task decomposition following the examples provided."""},
                {"role": "user", "content": curr_prompt}
            ]
            _, text = LM(messages,args.gpt_version, max_tokens=1300, frequency_penalty=0.0)

            # Post-processing: markdown 블록 제거
            if text.startswith("```python"):
                text = text[len("```python"):].strip()
            if text.startswith("```"):
                text = text[3:].strip()
            if text.endswith("```"):
                text = text[:-3].strip()

        decomposed_plan.append(text)
        
    print ("Generating Allocation Solution...")

    ######## Train Task Allocation - SOLUTION ########
    prompt = f"from skills import " + actions.ai2thor_actions
    prompt += f"\nimport time"
    prompt += f"\nimport threading"
    
    prompt_file = os.getcwd() + "/data/pythonic_plans/" + args.prompt_allocation_set + "_solution.py"
    allocated_prompt_file = open(prompt_file, "r")
    allocated_prompt = allocated_prompt_file.read()
    allocated_prompt_file.close()
    
    prompt += "\n\n" + allocated_prompt + "\n\n"
    
    allocated_plan = []
    for i, plan in enumerate(decomposed_plan):
        no_robot  = len(available_robots[i])
        curr_prompt = prompt + plan
        curr_prompt += f"\n\n{'='*80}"
        curr_prompt += f"\n# ABOVE ARE EXAMPLES ONLY - IGNORE THEM NOW!"
        curr_prompt += f"\n# YOUR CURRENT TASK: \"{test_tasks[i]}\""
        curr_prompt += f"\n# Allocate robots for THIS task ONLY (not the examples above)."
        curr_prompt += f"\n{'='*80}"
        curr_prompt += f"\n\n# TASK ALLOCATION"
        curr_prompt += f"\n# Scenario: There are {no_robot} robots available, The task should be performed using the minimum number of robots necessary. Robots should be assigned to subtasks that match its skills and mass capacity. Using your reasoning come up with a solution to satisfy all contraints."
        curr_prompt += f"\n\nrobots = {available_robots[i]}"
        curr_prompt += f"\n{objects_ai}"
        curr_prompt += f"\n\n# IMPORTANT: The AI should ensure that the robots assigned to the tasks have all the necessary skills to perform the tasks. IMPORTANT: Determine whether the subtasks must be performed sequentially or in parallel, or a combination of both and allocate robots based on availablitiy. "
        curr_prompt += f"\n# SOLUTION  \n"

        if "gpt" not in args.gpt_version:
            # older versions of GPT
            _, text = LM(curr_prompt, args.gpt_version, max_tokens=1000, stop=["def"], frequency_penalty=0.65)

        elif "gpt-3.5" in args.gpt_version:
            # gpt 3.5 and its variants
            messages = [
                {"role": "system", "content": """You are a robot task allocation analyst.

        CRITICAL: You are given examples followed by a NEW task. You MUST allocate robots for the NEW task ONLY.
        DO NOT confuse the NEW task with the examples!

        STEP 1 - IDENTIFY THE CURRENT TASK:
        The current task is AFTER all examples and AFTER the decomposed code.
        Look for "# YOUR CURRENT TASK:" marker to find the exact task description.
        The decomposed plan function names/comments will also indicate the task.

        STEP 2 - ANALYZE REQUIRED SKILLS:
        From the decomposed plan code, identify ALL skills used:
        - PickupObject → needs robot with 'PickupObject' skill
        - PutObject → needs robot with 'PutObject' skill
        - SwitchOn/SwitchOff → needs robot with 'SwitchOn'/'SwitchOff' skills
        - SliceObject → needs robot with 'SliceObject' skill
        - OpenObject/CloseObject → needs robot with these skills
        - ThrowObject/BreakObject → needs robot with these skills

        STEP 3 - CHECK EACH ROBOT'S SKILLS:
        You will be given: robots = [{'name': 'robot1', 'skills': [...]}, ...]
        For EACH robot, list their skills explicitly.

        STEP 4 - MATCH SKILLS TO ROBOTS:
        Rule 1: If ONE robot has ALL required skills → Assign ONLY that robot
        Rule 2: If NO robot has all skills → Form MINIMUM team
        Rule 3: IGNORE robots whose skills are not needed for the task
        Rule 4: For sequential tasks (pickup → wash → place), team robots must coordinate

        CRITICAL EXAMPLE - Wash and Place Task:
        Task: "Wash the fork and put it in the bowl"
        Required skills: PickupObject, PutObject (for fork manipulation) + SwitchOn, SwitchOff (for faucet)

        Given robots:
        - Robot1: [GoToObject, BreakObject, ThrowObject] ← NO required skills, CANNOT help
        - Robot2: [GoToObject, SwitchOn, SwitchOff] ← Has faucet control only
        - Robot3: [GoToObject, PickupObject, PutObject] ← Has object manipulation only

        Analysis:
        - Robot1 has NO required skills (BreakObject, ThrowObject not needed) → EXCLUDE
        - Robot2 can control faucet but CANNOT pickup/place fork → PARTIAL
        - Robot3 can pickup/place fork but CANNOT control faucet → PARTIAL
        - Team [Robot2, Robot3] has ALL skills → SELECT THIS TEAM

        Solution: "Team of Robots 2 and 3 will perform this task. Robot 3 handles picking up and placing the fork (PickupObject, PutObject). Robot 2 controls the faucet (SwitchOn, SwitchOff). Robot 1 cannot help as it lacks required skills."

        STEP 5 - WRITE YOUR ANALYSIS (EXACT FORMAT):
        Line 1: "**Task:** [exact task description]"
        Line 2: "Required skills for this task: [list ALL skills from decomposed plan]"
        Line 3-N: For EACH robot, state: "Robot X has: [their skills] - [Can/Cannot help because...]"
        Last lines: "Team of Robots [X and Y] will perform this task. [Explain skill distribution]"

        FORBIDDEN MISTAKES:
        - DO NOT use robots that lack required skills
        - DO NOT confuse example tasks with the current task
        - DO NOT use objects not mentioned in the current task
        - DO NOT assign same sequential actions to different robots"""},
                {"role": "user", "content": curr_prompt}
            ]
            _, text = LM(messages, args.gpt_version, max_tokens=1500, frequency_penalty=0.35)

        else:
            # gpt 4.0
            messages = [
                {"role": "system", "content": """You are a Robot Task Allocation Expert.

        CRITICAL OUTPUT FORMAT RULES:
        1. Output plain text analysis only - NO markdown
        2. NEVER use code blocks (```python or ```)
        3. Write natural language reasoning only

        CRITICAL OBJECT MATCHING:
        1. Use ONLY objects EXPLICITLY mentioned in the task description
        2. NEVER substitute or invent objects (e.g., if task says "Spatula", use ONLY Spatula)
        3. Read the task description carefully to identify the EXACT objects

        CRITICAL CONSTRAINTS:
        1. Robots CANNOT pass objects to each other
        2. A robot that picks up an object MUST complete all actions with that object
        3. For SEQUENTIAL tasks (pickup → action → put), assign ONE robot only
        4. Use multiple robots ONLY for PARALLEL independent subtasks

        SKILL MATCHING RULES:
        1. SliceObject tasks: Robot needs 'SliceObject' + 'PickupObject' (for Knife) skills
        2. ThrowObject tasks: Robot needs 'ThrowObject' + 'PickupObject' skills, OR team of two robots
        3. Wash+Place tasks: Robot needs 'PickupObject' + 'PutObject' + 'SwitchOn' + 'SwitchOff' skills
        4. Check each robot's skill list carefully before assigning

        MASS CAPACITY RULES:
        1. Check if robot mass capacity >= object mass
        2. If not, form robot teams with combined mass capacity
        3. All team members must have compatible skills

        Determine whether the subtasks must be performed sequentially or in parallel based on reasoning."""},
                {"role": "system", "content": "You are a Robot Task Allocation Expert"},
                {"role": "user", "content": curr_prompt}
            ]
            _, text = LM(messages, args.gpt_version, max_tokens=500, frequency_penalty=0.69)

        # Post-processing: markdown 블록 제거
        if text.startswith("```python"):
            text = text[len("```python"):].strip()
        if text.startswith("```"):
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

        allocated_plan.append(text)
    
    print ("Generating Allocated Code...")
    
    ######## Train Task Allocation - CODE Solution ########

    prompt = f"from skills import " + actions.ai2thor_actions
    prompt += f"\nimport time"
    prompt += f"\nimport threading"
    prompt += objects_ai
    
    code_plan = []

    prompt_file1 = os.getcwd() + "/data/pythonic_plans/" + args.prompt_allocation_set + "_code.py"
    code_prompt_file = open(prompt_file1, "r")
    code_prompt = code_prompt_file.read()
    code_prompt_file.close()
    
    prompt += "\n\n" + code_prompt + "\n\n"

    for i, (plan, solution) in enumerate(zip(decomposed_plan,allocated_plan)):
        curr_prompt = prompt + plan # Stage 1 결과 
        curr_prompt += f"\n# TASK ALLOCATION"
        curr_prompt += f"\n\nrobots = {available_robots[i]}"
        curr_prompt += solution
        curr_prompt += f"\n# CODE Solution  \n"
        
        if "gpt" not in args.gpt_version:
            # older versions of GPT
            _, text = LM(curr_prompt, args.gpt_version, max_tokens=1000, stop=["def"], frequency_penalty=0.30)
        elif "gpt-3.5" in args.gpt_version:
            # gpt-3.5: needs simpler, more explicit prompts

            # Extract all function definitions from decomposed plan
            import re
            function_defs = re.findall(r'def\s+(\w+)\(', plan)

            messages = [
                {"role": "system", "content": f"""You are a Python code generator for robot tasks.

            CRITICAL WARNING - DO NOT COPY TRAINING EXAMPLES:
            You will see training examples (wash_fork, put_tomato, slice_potato, pick_up_fork).
            THESE ARE EXAMPLES ONLY - DO NOT INCLUDE THEM IN YOUR OUTPUT!
            Generate code ONLY for the task specified after "# TASK ALLOCATION" section.

            OUTPUT FORMAT:
            - Output ONLY Python code (no markdown, no ```)
            - Start with def, end with function call
            - Generate code ONLY for the current task (not training examples)

            CRITICAL REQUIREMENT - GENERATE ALL FUNCTIONS:
            The decomposed plan has {len(function_defs)} function(s): {', '.join(function_defs)}
            YOU MUST generate code for ALL {len(function_defs)} functions.
            DO NOT skip any functions from the decomposed plan!
            DO NOT include training example functions!

            CRITICAL RULES (READ CAREFULLY):
            1. TASK OBJECT RULE: Look at the task description. Use ONLY those exact objects.
               Example: "Throw the Spatula" → Use 'Spatula' ONLY (NOT Fork, NOT Spoon)

            2. AVAILABLE ACTIONS - USE ONLY THESE (NO OTHER FUNCTIONS EXIST):
               ✓ GoToObject(robot, 'ObjectName')              # 2 args
               ✓ OpenObject(robot, 'ObjectName')              # 2 args
               ✓ CloseObject(robot, 'ObjectName')             # 2 args
               ✓ BreakObject(robot, 'ObjectName')             # 2 args
               ✓ PickupObject(robot, 'ObjectName')            # 2 args
               ✓ PutObject(robot, 'ObjectName', 'Receptacle') # 3 args
               ✓ ThrowObject(robot, 'ObjectName')             # 2 args (NO receptacle)
               ✓ SliceObject(robot, 'ObjectName')             # 2 args
               ✓ CleanObject(robot, 'ObjectName')             # 2 args
               ✓ SwitchOn(robot, 'ObjectName')                # 2 args
               ✓ SwitchOff(robot, 'ObjectName')               # 2 args

               DO NOT USE: DropHandObject, PushObject, PullObject (NOT implemented!)

            3. ROBOT PARAMETER RULE - CRITICAL:
               ALWAYS use robot_list[0], robot_list[1], etc. NEVER pass robot_list directly.

               SINGLE ROBOT (most common):
               def task(robot_list):
                   GoToObject(robot_list[0], 'Object')  # Use robot_list[0]
                   PickupObject(robot_list[0], 'Object')
               task([robots[0]])  # Pass ONE robot

               TEAM ROBOT (for heavy objects):
               def task(robot_list):
                   # robot_list[0] does main work, robot_list[1] assists
                   GoToObject(robot_list[0], 'HeavyObject')
                   PickupObject(robot_list[0], 'HeavyObject')  # Still use [0]
               task([robots[0], robots[1]])  # Pass TWO robots

               PARALLEL TASKS (independent subtasks):
               def task1(robot_list):
                   GoToObject(robot_list[0], 'Object1')
               def task2(robot_list):
                   GoToObject(robot_list[0], 'Object2')

               task1_thread = threading.Thread(target=task1, args=([robots[0]],))
               task2_thread = threading.Thread(target=task2, args=([robots[1]],))
               task1_thread.start()
               task2_thread.start()
               task1_thread.join()
               task2_thread.join()

            4. SLICE RULE: Get Knife FIRST
               def slice_tomato(robot_list):
                   GoToObject(robot_list[0], 'Knife')
                   PickupObject(robot_list[0], 'Knife')
                   GoToObject(robot_list[0], 'Tomato')
                   SliceObject(robot_list[0], 'Tomato')
               slice_tomato([robots[0]])

            5. WASH+PLACE WITH TEAM (different robots for different skills):
               CRITICAL: If allocation says "Team of Robots X and Y":
               - Check which robot does object manipulation (PickupObject, PutObject)
               - Check which robot controls switches (SwitchOn, SwitchOff)
               - Assign robot_list[0] to switch robot, robot_list[1] to manipulation robot

               Example - Team of Robot2 (switch) and Robot3 (pickup/put):
               def wash_fork_and_put_in_bowl(robot_list):
                   # robot_list = [robot2, robot3]
                   # Robot3 (robot_list[1]) does pickup/put
                   GoToObject(robot_list[1], 'Fork')
                   PickupObject(robot_list[1], 'Fork')
                   GoToObject(robot_list[1], 'Sink')
                   PutObject(robot_list[1], 'Fork', 'Sink')
                   # Robot2 (robot_list[0]) does switch
                   SwitchOn(robot_list[0], 'Faucet')
                   time.sleep(5)
                   SwitchOff(robot_list[0], 'Faucet')
                   # Robot3 (robot_list[1]) picks up again and places
                   PickupObject(robot_list[1], 'Fork')
                   GoToObject(robot_list[1], 'Bowl')
                   PutObject(robot_list[1], 'Fork', 'Bowl')
               # Pass robots in ORDER: [switch_robot, manipulation_robot]
               wash_fork_and_put_in_bowl([robots[1], robots[2]])

            6. SINGLE ROBOT WASH (if one robot has all skills):
               def wash_place_lettuce(robot_list):
                   GoToObject(robot_list[0], 'Lettuce')
                   PickupObject(robot_list[0], 'Lettuce')
                   GoToObject(robot_list[0], 'Sink')
                   PutObject(robot_list[0], 'Lettuce', 'Sink')
                   SwitchOn(robot_list[0], 'Faucet')
                   SwitchOff(robot_list[0], 'Faucet')
                   GoToObject(robot_list[0], 'Lettuce')
                   PickupObject(robot_list[0], 'Lettuce')
                   GoToObject(robot_list[0], 'CounterTop')
                   PutObject(robot_list[0], 'Lettuce', 'CounterTop')
               wash_place_lettuce([robots[0]])

            GENERATE CODE FOR THE TASK IN "# TASK ALLOCATION" SECTION ONLY.
            Use objects from task description ONLY.
            Follow function signatures EXACTLY.
            No markdown blocks.

            CRITICAL - READ THE ALLOCATION SOLUTION:
            The allocation solution tells you WHICH robots are assigned.
            Look for phrases like:
            - "Robot X will perform" → Use robots[X-1] (e.g., Robot 2 → robots[1])
            - "Team of Robots X and Y" → Use [robots[X-1], robots[Y-1]]
            - Check which robot has which skills to assign robot_list[0] vs robot_list[1]

            For "Wash fork and put in bowl" with Team of Robots 2 and 3:
            - Robot 2 has SwitchOn/SwitchOff → robot_list[0] for switches
            - Robot 3 has PickupObject/PutObject → robot_list[1] for manipulation
            - Function call: wash_fork([robots[1], robots[2]]) ← indices are 1 and 2 (0-based)

            CRITICAL: You MUST generate:
            1. ALL {len(function_defs)} function definitions: {', '.join(function_defs)}
            2. EVERY function MUST have robot_list parameter
            3. Assign robot_list[0], [1] based on their skills from allocation solution
            4. Function CALLS at the end with correct robots[] indices

            Example - TWO functions:
            def task1(robot_list):  # MUST have robot_list
                GoToObject(robot_list[0], 'Object')  # MUST use [0]
            def task2(robot_list):  # MUST have robot_list
                SwitchOn(robot_list[0], 'Light')  # MUST use [0]

            # Execute ALL functions
            task1([robots[0]])
            task2([robots[0]])

            DO NOT forget:
            - robot_list parameter in EVERY function
            - robot_list[0] in EVERY action
            - function calls for ALL functions

            CRITICAL INSTRUCTION:
            Everything ABOVE THIS LINE are EXAMPLES ONLY - DO NOT copy them!
            Generate code ONLY for the task in the "# TASK ALLOCATION" section below.
            The task name and robots are specified there.
            DO NOT generate code for wash_fork, put_tomato_in_fridge, slice_potato, or pick_up_fork examples!"""},
                {"role": "user", "content": curr_prompt + f"\n\n{'='*80}\n# ABOVE ARE EXAMPLES - IGNORE THEM\n# GENERATE CODE FOR THIS TASK ONLY:\n{'='*80}\n\n# Generate Python code for the task in TASK ALLOCATION section.\n# Include ALL {len(function_defs)} functions AND their function calls:\n"}
            ]
            _, text = LM(messages, args.gpt_version, max_tokens=1000, frequency_penalty=0.5)
        else:
            # using gpt-4 or other advanced models
            messages = [
                {"role": "system", "content": """You are a Python code generator for multi-robot task allocation.

            CRITICAL OUTPUT FORMAT RULES:
            1. Output MUST start directly with Python code (def or function calls)
            2. NEVER use markdown code blocks (```python or ```)
            3. NEVER add any text before or after the code
            4. NEVER add explanations, comments outside the code, or formatting
            5. Output ONLY raw executable Python code that can be directly run

            CRITICAL CODING RULES:
            1. Generate ONLY executable Python code - NO text explanations
            2. MUST use robot_list parameter in ALL function definitions
            3. MUST pass robots to ALL action functions: GoToObject(robot_list[0], 'Object')
            4. Generate code ONLY for the current task in TASK ALLOCATION section
            5. Do NOT generate code for examples - only for the task being analyzed
            6. Follow the EXACT format from the CODE Solution examples above
            7. CRITICAL: Use ONLY objects EXPLICITLY MENTIONED in the task description
            8. NEVER reference objects not mentioned in the task (e.g., if task says "Spatula", use ONLY Spatula, NOT Fork/Spoon)
            9. NEVER invent or assume objects - use EXACTLY what the task specifies
            10. If CounterTop exists, use it instead of DiningTable for placing objects
            11. CRITICAL: A robot that PickupObject MUST also PutObject/ThrowObject the SAME object
            12. NEVER use different robot indices (robot_list[0] vs robot_list[1]) for pickup and put/throw of SAME object
            13. For SEQUENTIAL tasks (pickup → action → put), use robot_list[0] for ALL actions
            14. CRITICAL: Before SliceObject, MUST first get Knife: GoToObject(robot, 'Knife') then PickupObject(robot, 'Knife')
            15. CRITICAL: Every object manipulation action requires GoToObject first

            FUNCTION SIGNATURES (EXACT usage required):
            - GoToObject(robot, 'ObjectName')           # Takes 2 args
            - PickupObject(robot, 'ObjectName')         # Takes 2 args
            - PutObject(robot, 'ObjectName', 'Receptacle')  # Takes 3 args
            - ThrowObject(robot, 'ObjectName')          # Takes 2 args ONLY (no receptacle)
            - SliceObject(robot, 'ObjectName')          # Takes 2 args
            - BreakObject(robot, 'ObjectName')          # Takes 2 args
            - SwitchOn(robot, 'ObjectName')             # Takes 2 args
            - SwitchOff(robot, 'ObjectName')            # Takes 2 args
            - OpenObject(robot, 'ObjectName')           # Takes 2 args
            - CloseObject(robot, 'ObjectName')          # Takes 2 args

            REQUIRED FORMAT FOR SEQUENTIAL TASKS (no markdown, just code):
            def task_name(robot_list):
                # Use robot_list[0] for ENTIRE sequence
                GoToObject(robot_list[0], 'Object1')
                PickupObject(robot_list[0], 'Object1')
                GoToObject(robot_list[0], 'Receptacle')
                PutObject(robot_list[0], 'Object1', 'Receptacle')

            # For sequential tasks: Use ONE robot
            task_name([robots[0]])

            REQUIRED FORMAT FOR SLICE ACTIONS (must have knife first):
            def slice_object(robot_list):
                # MUST get knife first
                GoToObject(robot_list[0], 'Knife')
                PickupObject(robot_list[0], 'Knife')
                # Then go to target object
                GoToObject(robot_list[0], 'Tomato')
                SliceObject(robot_list[0], 'Tomato')

            slice_object([robots[0]])

            REQUIRED FORMAT FOR THROW ACTIONS:
            def throw_object_in_trash(robot_list):
                # Robot with PickupObject skill picks up
                GoToObject(robot_list[0], 'Spatula')
                PickupObject(robot_list[0], 'Spatula')
                GoToObject(robot_list[0], 'GarbageCan')
                # ThrowObject takes 2 args ONLY
                ThrowObject(robot_list[0], 'Spatula')

            throw_object_in_trash([robots[0]])

            REQUIRED FORMAT FOR WASH + PLACE (single robot for entire sequence):
            def wash_and_place_lettuce(robot_list):
                # Same robot does EVERYTHING
                GoToObject(robot_list[0], 'Lettuce')
                PickupObject(robot_list[0], 'Lettuce')
                GoToObject(robot_list[0], 'Sink')
                PutObject(robot_list[0], 'Lettuce', 'Sink')
                SwitchOn(robot_list[0], 'Faucet')
                SwitchOff(robot_list[0], 'Faucet')
                GoToObject(robot_list[0], 'Lettuce')
                PickupObject(robot_list[0], 'Lettuce')
                GoToObject(robot_list[0], 'CounterTop')
                PutObject(robot_list[0], 'Lettuce', 'CounterTop')

            wash_and_place_lettuce([robots[0]])

            FORBIDDEN:
            - Markdown code blocks (```python or ```)
            - Any text outside Python code
            - Using objects NOT mentioned in task description
            - Wrong function signatures (e.g., ThrowObject with 3 args)
            - Different robots for pickup and put/throw of same object
            - SliceObject without getting Knife first
            - Sequential tasks split across multiple robots"""},
                {"role": "user", "content": curr_prompt + "\n\n# CODE Solution (output raw Python code only, NO markdown blocks):\n"}
            ]
            _, text = LM(messages, args.gpt_version, max_tokens=1400, frequency_penalty=0.4)

            # Post-processing: markdown 블록 제거 (만약 LLM이 여전히 생성한다면)
            if text.startswith("```python"):
                text = text[len("```python"):].strip()
            if text.startswith("```"):
                text = text[3:].strip()
            if text.endswith("```"):
                text = text[:-3].strip()

        code_plan.append(text)
    
    # save generated plan
    exec_folders = []
    if args.log_results:
        line = {}
        now = datetime.now() # current date and time
        date_time = now.strftime("%m-%d-%Y-%H-%M-%S")
        
        for idx, task in enumerate(test_tasks):
            task_name = "{fxn}".format(fxn = '_'.join(task.split(' ')))
            task_name = task_name.replace('\n','')
            folder_name = f"{task_name}_plans_{date_time}"
            exec_folders.append(folder_name)
            
            os.mkdir("./logs/"+folder_name)
     
            with open(f"./logs/{folder_name}/log.txt", 'w') as f:
                f.write(task)
                f.write(f"\n\nGPT Version: {args.gpt_version}")
                f.write(f"\n\nFloor Plan: {args.floor_plan}")
                f.write(f"\n{objects_ai}")
                f.write(f"\nrobots = {available_robots[idx]}")
                f.write(f"\nground_truth = {gt_test_tasks[idx]}")
                f.write(f"\ntrans = {trans_cnt_tasks[idx]}")
                f.write(f"\nmax_trans = {max_trans_cnt_tasks[idx]}")

            with open(f"./logs/{folder_name}/decomposed_plan.py", 'w') as d:
                d.write(decomposed_plan[idx])
                
            with open(f"./logs/{folder_name}/allocated_plan.py", 'w') as a:
                a.write(allocated_plan[idx])
                
            with open(f"./logs/{folder_name}/code_plan.py", 'w') as x:
                x.write(code_plan[idx])
            