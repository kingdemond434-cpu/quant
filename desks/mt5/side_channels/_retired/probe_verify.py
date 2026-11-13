import json, inspect
src = open('research/verify_universal_state.py', encoding='utf-8').read()
print('dec in pulls:', 'dec(msg2)' in src)
print('bytes cat-file:', 'binary=True' in src)
out = {'holds': []}
pulls = []
rc2, msg2 = 1, b'Aborting'
pulls.append({"action": "merge -X theirs", "ok": rc2 == 0,
              "detail": (str(msg2).strip().splitlines() or [""])[-1]})
out['pull'] = pulls
try:
    json.dumps(out)
    print('json ok')
except TypeError as e:
    print('json fail:', e)