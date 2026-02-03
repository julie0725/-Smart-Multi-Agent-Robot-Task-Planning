#!/bin/bash

# SMART-LLM Unified Benchmark Script
# Usage:
#   ./run_benchmark.sh generate
#   ./run_benchmark.sh execute
#   ./run_benchmark.sh full
#   ./run_benchmark.sh single  <floor> [gpt_ver] [contains]
#   ./run_benchmark.sh singlei <floor> [gpt_ver] <index>

set -e

MODE=$1
FLOORPLANS=(6 15 21 201 209 303 414)

# CHANGED: 전역 GPT_VERSION / TASK_* 제거 (모드별로 함수 안에서 로컬로 파싱)
# GPT_VERSION=${3:-gpt-4}
# TASK_CONTAINS=$4
# TASK_INDEX=$4

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ========================================
# Mode 1: Generate code only
# ========================================
generate_all() {
    # CHANGED: generate 모드에서 gpt 버전은 $2로 받거나 기본값 사용
    GPT_VERSION_LOCAL=${2:-gpt-4}

    echo "=========================================="
    echo "SMART-LLM Code Generation"
    echo "GPT Version: ${GPT_VERSION_LOCAL}"
    echo "FloorPlans: ${FLOORPLANS[@]}"
    echo "=========================================="
    echo ""

    TOTAL_SUCCESS=0
    TOTAL_FAIL=0

    for FLOOR in "${FLOORPLANS[@]}"; do
        echo "=========================================="
        echo "Running FloorPlan ${FLOOR}..."
        echo "=========================================="

        # CHANGED: 로컬 GPT_VERSION 사용
        python3 scripts/run_llm.py --floor-plan ${FLOOR} --gpt-version ${GPT_VERSION_LOCAL} --log-results 1
        EXIT_CODE=$?

        if [ $EXIT_CODE -eq 0 ]; then
            echo -e "${GREEN}✓ FloorPlan ${FLOOR} completed successfully${NC}"
            TOTAL_SUCCESS=$((TOTAL_SUCCESS + 1))
        else
            echo -e "${RED}✗ FloorPlan ${FLOOR} failed with exit code ${EXIT_CODE}${NC}"
            TOTAL_FAIL=$((TOTAL_FAIL + 1))
        fi

        echo ""
        sleep 3
    done

    echo "=========================================="
    echo "CODE GENERATION COMPLETE"
    echo "=========================================="
    echo "Success: ${TOTAL_SUCCESS}/${#FLOORPLANS[@]}"
    echo "Failed:  ${TOTAL_FAIL}/${#FLOORPLANS[@]}"
    echo "=========================================="
}

# ========================================
# Mode 2: Execute all generated plans
# ========================================
execute_all() {
    echo "=========================================="
    echo "Executing All Plans in AI2-THOR"
    echo "=========================================="
    echo ""

    TOTAL=0
    SUCCESS=0
    FAIL=0

    for task_dir in logs/*/; do
        TOTAL=$((TOTAL + 1))
        task_name=$(basename "$task_dir")

        echo "=========================================="
        echo "[$TOTAL] Executing: $task_name"
        echo "=========================================="

        # Execute with timeout (2 minutes per task)
        set +e  #  CHANGED: set -e 때문에 timeout/실행 실패 시 루프가 깨지는 것 방지
        timeout 120 python3 scripts/execute_plan.py --command "$task_name"
        EXIT_CODE=$?
        set -e

        if [ $EXIT_CODE -eq 0 ]; then
            echo -e "${GREEN}✓ SUCCESS: $task_name${NC}"
            SUCCESS=$((SUCCESS + 1))

            if ls "$task_dir"video_*.mp4 1> /dev/null 2>&1; then
                echo "  Videos saved:"
                ls -lh "$task_dir"video_*.mp4 | awk '{print "    " $9 " (" $5 ")"}'
            else
                echo -e "  ${YELLOW}WARNING: No video files found${NC}"
            fi
        elif [ $EXIT_CODE -eq 124 ]; then
            echo -e "${RED}✗ TIMEOUT: $task_name (120s)${NC}"
            FAIL=$((FAIL + 1))
        else
            echo -e "${RED}✗ FAILED: $task_name (exit code: $EXIT_CODE)${NC}"
            FAIL=$((FAIL + 1))
        fi

        echo ""
        sleep 2
    done

    echo "=========================================="
    echo "EXECUTION COMPLETE"
    echo "=========================================="
    echo "Total:   $TOTAL tasks"
    echo -e "${GREEN}Success: $SUCCESS tasks${NC}"
    echo -e "${RED}Failed:  $FAIL tasks${NC}"
    echo "=========================================="
    echo ""
    echo "Videos location: logs/<task_name>/video_*.mp4"
}

# ========================================
# Mode 3: Full benchmark (generate + execute)
# ========================================
full_benchmark() {
    # CHANGED: full 모드에서 gpt 버전은 $2로 받거나 기본값 사용
    GPT_VERSION_LOCAL=${2:-gpt-4}

    RESULT_DIR="benchmark_results_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$RESULT_DIR"
    LOG_FILE="$RESULT_DIR/benchmark_log.txt"

    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║         SMART-LLM Full Benchmark (${GPT_VERSION_LOCAL})           ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""

    TOTAL_TASKS=0
    for floor in "${FLOORPLANS[@]}"; do
        task_count=$(wc -l < "data/final_test/FloorPlan${floor}.json")
        TOTAL_TASKS=$((TOTAL_TASKS + task_count))
    done

    # 비용 추정(예시 유지)
    if [ "$GPT_VERSION_LOCAL" = "gpt-4" ]; then
        ESTIMATED_COST=$(echo "scale=2; $TOTAL_TASKS * 0.04" | bc)
    else
        ESTIMATED_COST=$(echo "scale=2; $TOTAL_TASKS * 0.005" | bc)
    fi

    echo "Total tasks: $TOTAL_TASKS"
    echo "Estimated cost: \$$ESTIMATED_COST"
    echo ""
    read -p "Continue? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 1
    fi

    if [ -d "logs" ] && [ "$(ls -A logs)" ]; then
        echo "Backing up existing logs..."
        backup_dir="logs_backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$backup_dir"
        mv logs/* "$backup_dir"/ 2>/dev/null
    fi

    echo "" | tee -a "$LOG_FILE"
    echo "Starting benchmark..." | tee -a "$LOG_FILE"
    echo "Start time: $(date)" | tee -a "$LOG_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" | tee -a "$LOG_FILE"

    echo "" | tee -a "$LOG_FILE"
    echo "Phase 1: Generating code..." | tee -a "$LOG_FILE"
    # CHANGED: generate_all에 gpt 버전 전달
    generate_all "$GPT_VERSION_LOCAL" 2>&1 | tee -a "$LOG_FILE"

    echo "" | tee -a "$LOG_FILE"
    echo "🎬 Phase 2: Executing plans..." | tee -a "$LOG_FILE"
    execute_all 2>&1 | tee -a "$LOG_FILE"

    echo "" | tee -a "$LOG_FILE"
    echo "Benchmark complete!" | tee -a "$LOG_FILE"
    echo "End time: $(date)" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    echo "Results saved to: $RESULT_DIR"
    echo "   Full log: $LOG_FILE"
}

# ========================================
# Mode 4a: Single FloorPlan with retry (substring filter)
# ========================================
single_with_retry() {
    FLOOR_PLAN=$2
    GPT_VERSION_LOCAL=${3:-gpt-4}
    TASK_CONTAINS_LOCAL=$4
    MAX_RETRIES=10
    RETRY_DELAY=60

    if [ -z "$FLOOR_PLAN" ]; then
        echo "Error: FloorPlan number required"
        echo "Usage: $0 single <floor_plan> [gpt_version] [task_contains]"
        exit 1
    fi

    echo "=== Running FloorPlan ${FLOOR_PLAN} with ${GPT_VERSION_LOCAL} ==="
    echo "Max retries: ${MAX_RETRIES}, Retry delay: ${RETRY_DELAY}s"
    if [ -n "$TASK_CONTAINS_LOCAL" ]; then
        echo "Task filter (contains): ${TASK_CONTAINS_LOCAL}"
    fi
    echo ""

    for i in $(seq 1 $MAX_RETRIES); do
        echo "Attempt $i/$MAX_RETRIES at $(date)"

        set +e
        if [ -n "$TASK_CONTAINS_LOCAL" ]; then
            python3 scripts/run_llm.py \
                --floor-plan ${FLOOR_PLAN} \
                --gpt-version ${GPT_VERSION_LOCAL} \
                --log-results 1 \
                --task-contains "$TASK_CONTAINS_LOCAL"
        else
            python3 scripts/run_llm.py \
                --floor-plan ${FLOOR_PLAN} \
                --gpt-version ${GPT_VERSION_LOCAL} \
                --log-results 1
        fi
        EXIT_CODE=$?
        set -e

        if [ $EXIT_CODE -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✓ SUCCESS: FloorPlan ${FLOOR_PLAN} completed!${NC}"
            exit 0
        else
            echo ""
            echo -e "${RED}✗ FAILED with exit code ${EXIT_CODE}${NC}"

            if [ $i -lt $MAX_RETRIES ]; then
                echo "Waiting ${RETRY_DELAY} seconds before retry..."
                sleep ${RETRY_DELAY}
            fi
        fi
    done

    echo ""
    echo -e "${RED}✗ FAILED: Maximum retries ($MAX_RETRIES) exceeded${NC}"
    exit 1
}

# ========================================
# Mode 4b: Single FloorPlan with retry (index filter, 0-based)
# ========================================
single_with_retry_index() {
    FLOOR_PLAN=$2
    GPT_VERSION_LOCAL=${3:-gpt-4}   # CHANGED: 전역 GPT_VERSION 대신 로컬 사용
    TASK_INDEX_LOCAL=$4             # CHANGED: 전역 TASK_INDEX 대신 로컬 사용
    MAX_RETRIES=10
    RETRY_DELAY=60

    if [ -z "$FLOOR_PLAN" ] || [ -z "$TASK_INDEX_LOCAL" ]; then
        echo "Error: FloorPlan number and task index required"
        echo "Usage: $0 singlei <floor_plan> [gpt_version] <task_index>"
        exit 1
    fi

    echo "=== Running FloorPlan ${FLOOR_PLAN} with ${GPT_VERSION_LOCAL} ==="
    echo "Max retries: ${MAX_RETRIES}, Retry delay: ${RETRY_DELAY}s"
    echo "Task filter (index, 0-based): ${TASK_INDEX_LOCAL}"
    echo ""

    for i in $(seq 1 $MAX_RETRIES); do
        echo "Attempt $i/$MAX_RETRIES at $(date)"

        # CHANGED: set -e 때문에 실패 시 즉시 종료되는 것 방지
        set +e
        python3 scripts/run_llm.py \
            --floor-plan ${FLOOR_PLAN} \
            --gpt-version ${GPT_VERSION_LOCAL} \
            --log-results 1 \
            --task-index "$TASK_INDEX_LOCAL"
        EXIT_CODE=$?
        set -e

        if [ $EXIT_CODE -eq 0 ]; then
            echo ""
            echo -e "${GREEN}✓ SUCCESS: FloorPlan ${FLOOR_PLAN} completed!${NC}"
            exit 0
        else
            echo ""
            echo -e "${RED}✗ FAILED with exit code ${EXIT_CODE}${NC}"

            if [ $i -lt $MAX_RETRIES ]; then
                echo "Waiting ${RETRY_DELAY} seconds before retry..."
                sleep ${RETRY_DELAY}
            fi
        fi
    done

    echo ""
    echo -e "${RED}✗ FAILED: Maximum retries ($MAX_RETRIES) exceeded${NC}"
    exit 1
}

# ========================================
# Main entry point
# ========================================
case "$MODE" in
    generate)
        # CHANGED: gpt 버전은 두 번째 인자로 선택 가능
        # 예: ./run_benchmark.sh generate gpt-3.5-turbo
        generate_all "$2"
        ;;
    execute)
        execute_all
        ;;
    full)
        # CHANGED: gpt 버전은 두 번째 인자로 선택 가능
        # 예: ./run_benchmark.sh full gpt-3.5-turbo
        full_benchmark "$2"
        ;;
    single)
        single_with_retry "$@"
        ;;
    singlei)
        single_with_retry_index "$@"
        ;;
    *)
        echo "SMART-LLM Unified Benchmark Script"
        echo ""
        echo "Usage:"
        echo "  $0 generate [gpt_version]                 Generate code for all FloorPlans"
        echo "  $0 execute                                Execute all generated plans"
        echo "  $0 full [gpt_version]                     Generate + Execute (complete benchmark)"
        echo "  $0 single <floor> [gpt_version] [contains]   Single FloorPlan + optional task substring filter"
        echo "  $0 singlei <floor> [gpt_version] <index>     Single FloorPlan + task index (0-based)"
        echo ""
        echo "Examples:"
        echo "  $0 generate"
        echo "  $0 generate gpt-3.5-turbo"
        echo "  $0 execute"
        echo "  $0 full gpt-3.5-turbo"
        echo "  $0 single 21 gpt-3.5-turbo \"Wash the fork\""
        echo "  $0 single 15 gpt-3.5-turbo \"Microwave a plate\""
        echo "  $0 singlei 21 gpt-3.5-turbo 3"
        exit 1
        ;;
esac
