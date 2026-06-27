#!/bin/bash

for i in $(seq 1 100); do
  #agentarts invoke '{"message": "hello,world"}' --session haolipeng &
  
  time curl https://1916215180918953.agentrun-data.cn-shanghai.aliyuncs.com/agent-runtimes/agent-code-AawC7/endpoints/Default/invocations/openai/v1/chat/completions -XPOST \
    -H "Content-Type: application/json" \
    -H "x-agentrun-session-id: $(uuidgen)" \
    -d '{
  "messages": [{"role": "user", "content": "hello?"}],
  "stream": true
}' &

  if (( i % 10 == 0 )); then
    wait
  fi
done
wait
