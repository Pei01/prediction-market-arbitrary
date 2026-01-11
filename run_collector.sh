#!/bin/bash

ASSETS=("BTC" "ETH" "SOL")

pids=()

echo "🚀 [System] 正在啟動所有 Collector..."

for asset in "${ASSETS[@]}"; do
    python run_collector.py --asset "$asset" &
    
    pids+=($!)
    echo "   ✅ 啟動 $asset Collector (PID: $!)"
    
    sleep 1
done

echo "---------------------------------------------------"
echo "🎉 所有 Collector 已在背景執行！"
echo "🛑 按下 Ctrl+C 可以一次停止所有程式"
echo "---------------------------------------------------"

cleanup() {
    echo ""
    echo "🛑 [System] 正在關閉所有 Collector..."
    for pid in "${pids[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            echo "   已停止 PID: $pid"
        fi
    done
    echo "結束運行"
    exit 0
}

trap cleanup SIGINT SIGTERM

wait