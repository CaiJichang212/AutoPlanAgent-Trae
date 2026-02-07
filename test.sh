export PYTHONUNBUFFERED=1
cur_date=$(date "+%Y%m%d")
cur_time=$(date "+%H%M%S")
mkdir -p log/${cur_date}

# source .venv/bin/activate
python test_agent.py > log/${cur_date}/test_agent_${cur_time}.log 2>&1 &