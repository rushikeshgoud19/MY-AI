import sys
import subprocess
import asyncio
import json
import os
import time

try:
    from agents.task_planner_agent import TaskPlannerAgent
    from agents.action_executor_agent import ActionExecutorAgent
except ImportError:
    print("ERROR: Run this from the root of the MY-AI directory.")
    sys.exit(1)

def print_header(msg):
    print(f"\n\033[95m[Mizune OS] {msg}\033[0m")

def print_error(msg):
    print(f"\033[91m{msg}\033[0m")

async def self_heal_crash(command, stderr_output):
    print_header("CRASH DETECTED. ENGAGING AUTONOMOUS HEALING.")
    print("Analyzing stack trace...")

    # Load config for API keys
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}

    planner = TaskPlannerAgent(config)
    executor = ActionExecutorAgent(config)

    # Prepare the prompt for the Task Planner
    goal = f"""The user ran the command: `{' '.join(command)}`
It crashed with the following error output:
```
{stderr_output[-2000:]}
```
Analyze this stack trace. Identify which file caused the crash. 
Write a plan to fix the error directly in the source file using the `write_file` or `run_terminal_command` actions.
Do not ask for confirmation. Fix the code."""

    plan = await planner.create_plan(goal, "Terminal")

    if plan.get("error"):
        print_error(f"Brain failed to plan a fix: {plan['error']}")
        return False

    print_header(f"FIX PLAN GENERATED: {len(plan.get('steps', []))} steps.")
    for step in plan.get('steps', []):
        print(f"  -> {step.get('action')}: {step.get('description')}")

    print_header("EXECUTING FIX IN BACKGROUND...")
    
    # Execute the plan
    while True:
        step = planner.get_next_step()
        if not step or step.get("done"):
            break
            
        result = await executor.execute_step(step, {})
        if not result.get("success") and not result.get("abort"):
             print_error(f"Step failed: {result.get('error')}")
             # Could trigger replanning here, but let's keep it simple for v1
             
        planner.advance_step(result.get("success", False))

    print_header("PATCH APPLIED SUCCESSFULLY.")
    return True

async def main():
    if len(sys.argv) < 2:
        print("Usage: python mizune-run.py <command>")
        print("Example: python mizune-run.py python main.py")
        sys.exit(1)

    command = sys.argv[1:]
    print_header(f"Running command under God Mode: {' '.join(command)}")

    while True:
        # Run the command and pipe output
        process = subprocess.Popen(
            command,
            stdout=sys.stdout,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # We need to capture stderr to catch crashes
        stderr_output = []
        for line in process.stderr:
            sys.stderr.write(line)
            sys.stderr.flush()
            stderr_output.append(line)

        process.wait()

        if process.returncode != 0:
            full_error = "".join(stderr_output)
            print_header(f"Process exited with code {process.returncode}")
            
            # Engage Self-Healing
            healed = await self_heal_crash(command, full_error)
            
            if healed:
                print_header("RESTARTING PROCESS...")
                time.sleep(2)
                continue
            else:
                print_error("Could not automatically heal the crash.")
                break
        else:
            print_header("Process completed successfully.")
            break

if __name__ == "__main__":
    asyncio.run(main())
