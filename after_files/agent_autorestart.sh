while echo "Running"; do
    python agent.py devs
    return_code=$?
    if (( return_code != 0 )); then
        echo "agent crashed with exit code $return_code. Respawning.." >>/var/log/agent.log
        date >> /var/log/agent.log
    fi
    sleep 1
done
