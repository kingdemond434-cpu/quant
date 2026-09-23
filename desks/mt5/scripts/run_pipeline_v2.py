import subprocess

proc = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cd /home/quant/quant-platform && "
     "PYTHONPATH=desks/mt5:desks/mt5/sleeves:desks/mt5/side_channels "
     "YOUTUBE_API_KEY=AIzaSyAIudkX3epD1dJZKNPMIr5x6J_9ayTGBoc "
     "/home/quant/quant-platform/.venv/bin/python "
     "desks/mt5/side_channels/full_pipeline.py 2>&1"],
    capture_output=True, text=True, timeout=600
)
# Print everything
output = proc.stdout + proc.stderr
# Print last 200 lines
lines = output.split("\n")
for line in lines[-200:]:
    print(line)
