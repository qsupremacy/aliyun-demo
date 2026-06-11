#!/bin/bash

for i in $(seq 1 500); do
  #agentarts invoke '{"message": "hello,world"}' --session haolipeng &
  start=$(date +%s%3N)
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting request $i"
  
  curl https://1916215180918953.agentrun-data.cn-shanghai.aliyuncs.com/agent-runtimes/agent-code-AawC7/endpoints/Default/invocations/openai/v1/chat/completions -XPOST \
    -H "Content-Type: application/json" \
    -H "x-agentrun-session-id: $(uuidgen)" \
    -d '{
  "messages": [{"role": "user", "content": "hello?"}],
  "stream": true
}'

  end=$(date +%s%3N)
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Finished request $i - elapsed: $((end - start)) ms"  #--session-id 0cf0f627-baee-4e36-a302-b7f58e44da9c &
  if (( i % 5 == 0 )); then
    wait
  fi
done
wait
