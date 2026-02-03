#!/bin/bash

# Execute all generated plans in AI2-THOR simulator
# This will open Unity window and save videos for each task
set -x

cd /home/jooyeon/Desktop/ai2thor_project/SMART-LLM

echo "=========================================="
echo "Executing All Plans in AI2-THOR"
echo "=========================================="
echo ""

TOTAL=0
SUCCESS=0
FAIL=0

# Get all task directories
for task_dir in logs/*/; do
    TOTAL=$((TOTAL + 1))
    task_name=$(basename "$task_dir")

    echo "=========================================="
    echo "[$TOTAL] Executing: $task_name"
    echo "=========================================="

    # Execute the plan
    python3 scripts/execute_plan.py --command "$task_name"

    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✓ SUCCESS: $task_name"
        SUCCESS=$((SUCCESS + 1))

        # Check if videos were created
        if ls "$task_dir"video_*.mp4 1> /dev/null 2>&1; then
            echo "  Videos saved:"
            ls -lh "$task_dir"video_*.mp4 | awk '{print "    " $9 " (" $5 ")"}'
        else
            echo "  WARNING: No video files found"
        fi
    else
        echo "✗ FAILED: $task_name (exit code: $EXIT_CODE)"
        FAIL=$((FAIL + 1))
    fi

    echo ""
    sleep 2
done

echo "=========================================="
echo "EXECUTION COMPLETE"
echo "=========================================="
echo "Total:   $TOTAL tasks"
echo "Success: $SUCCESS tasks"
echo "Failed:  $FAIL tasks"
echo "=========================================="
echo ""
echo "Videos location: logs/<task_name>/video_*.mp4"
