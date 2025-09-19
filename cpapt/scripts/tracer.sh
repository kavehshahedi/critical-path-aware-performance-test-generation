#!/bin/bash
set -e

SESSION_NAME=""
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --session-name)
            SESSION_NAME="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "Unknown option: $1"
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

# Check if program command is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [--session-name NAME] [--output-dir DIR] <PROGRAM_COMMAND>"
    echo "Example: $0 --session-name mytrace --output-dir /tmp/traces ./my_application arg1 arg2"
    exit 1
fi

# Check if LTTng is available
if ! command -v lttng &> /dev/null; then
    echo "Error: LTTng is not installed or not in PATH"
    exit 1
fi

if [ -z "$SESSION_NAME" ]; then
    SESSION_NAME="app_perf_trace_$$"
fi

if [ -z "$OUTPUT_DIR" ]; then
    OUTPUT_DIR="$(pwd)/lttng-traces"
fi

TRACE_PATH="$OUTPUT_DIR/$SESSION_NAME"
PROGRAM_CMD="$@"

echo "Starting LTTng kernel tracing for: $PROGRAM_CMD"
echo "Session: $SESSION_NAME"
echo "Output: $TRACE_PATH"

cleanup() {
    echo "Cleaning up LTTng session..."
    lttng stop $SESSION_NAME 2>/dev/null || true
    lttng destroy $SESSION_NAME 2>/dev/null || true
}

trap cleanup EXIT

echo "Creating LTTng session..."
lttng create $SESSION_NAME --output=$TRACE_PATH

echo "Enabling CPU scheduling events..."
lttng enable-event --kernel sched_switch
lttng enable-event --kernel sched_process_exec
lttng enable-event --kernel sched_process_exit

echo "Enabling memory management events..."
lttng enable-event --kernel kmem_mm_page_alloc
lttng enable-event --kernel kmem_mm_page_free
lttng enable-event --kernel kmem_cache_alloc
lttng enable-event --kernel kmem_cache_free

echo "Enabling block I/O events..."
lttng enable-event --kernel block_rq_issue
lttng enable-event --kernel block_rq_complete

echo "Enabling additional low-overhead events..."
lttng enable-event --kernel --syscall --all
lttng enable-event --kernel net_dev_queue
lttng enable-event --kernel net_dev_xmit
lttng enable-event --kernel irq_entry
lttng enable-event --kernel irq_exit

echo "Starting tracing..."
lttng start

echo "Running application: $PROGRAM_CMD"

eval "$PROGRAM_CMD"

echo "Stopping tracing..."
lttng stop $SESSION_NAME