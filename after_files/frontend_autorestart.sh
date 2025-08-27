while echo "Running"; do
    cd /frontend && npm start >> /var/log/npm.log
    return_code=$?
    if (( return_code != 0 )); then
        echo "frontend crashed with exit code $return_code. Respawning.." >>/var/log/npm.log
        date >> /var/log/npm.log
    fi
    sleep 1
done
