import re

# Read the current file
with open('/home/quant/quant-platform/desks/mt5/research/shadow_forward.py', 'r') as f:
    content = f.read()

# Fix 1: Change partition_work to admit all declared sleeves (open shadow)
content = content.replace(
    '_work, _blocked = partition_work(_declared, BASE)',
    '_work, _blocked = _declared, []  # OPEN SHADOW: admit all declared sleeves for forward measurement'
)

# Fix 2: Update the gate_admission to be accurate
old_main_start = '''    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))'''
new_main_start = '''    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    # Load gate classification for accurate admission status
    from gate_classification import historical_certificate_status, validity_all_pass, power_deficiencies
    from pathlib import Path
    reports = BASE / "reports"
    def _load_hist_cert(key):
        import json
        qquant = json.loads((reports / "QQUANT_GATES.json").read_text("utf-8")) if (reports / "QQUANT_GATES.json").exists() else {}
        if qquant.get("gate_policy") == "mt5-original-universal-10-v2-calibrated-inputs":
            for row in qquant.get("verdicts", []):
                if not isinstance(row, dict): continue
                row_key = f"{row.get(\"sym\")} {row.get(\"fam\")} {row.get(\"side\")} {row.get(\"win\")} {row.get(\"cond\")}"
                if row_key == key:
                    return {"gates": row.get("stages", {})}
        real = json.loads((reports / "REAL_SURVIVORS.json").read_text("utf-8")) if (reports / "REAL_SURVIVORS.json").exists() else {}
        for row in real.get("real_survivors", []):
            if not isinstance(row, dict): continue
            row_key = f"{row.get(\"sym\")} {row.get(\"fam\")} {row.get(\"side\")} {row.get(\"win\")} {row.get(\"state\")}"
            if row_key == key:
                return {"gates": row.get("qquant_gates", {}).get("stages", {})}
        universal = json.loads((reports / "UNIVERSAL_SURVIVORS.json").read_text("utf-8")) if (reports / "UNIVERSAL_SURVIVORS.json").exists() else {}
        for cert in universal.get("survivors", {}).values():
            if not isinstance(cert, dict): continue
            spec = cert.get("shadow_spec")
            if not isinstance(spec, dict): continue
            cert_key = f"{spec.get(\"symbol\")} {spec.get(\"family\")} {spec.get(\"side\")} {spec.get(\"selector\")} {spec.get(\"condition\")}"
            if cert_key == key:
                return {"gates": cert.get("gates", {})}
        return None'''

content = content.replace(old_main_start, new_main_start)

# Fix 3: Replace the gate_admission assignment with accurate status
old_admission = '''        st["last_attempt_at"] = attempt_at
        st["gate_admission"] = "ORIGINAL_UNIVERSAL_10_PASS"
        if st.get("status") == "BLOCKED_UNIVERSAL_GATES":'''

new_admission = '''        st["last_attempt_at"] = attempt_at
        # Accurate admission status based on historical certificate
        hist_cert = _load_hist_cert(key)
        hist_status = historical_certificate_status(hist_cert) if hist_cert else None
        if hist_status and hist_status.get("validity_pass"):
            if not hist_status.get("power_deficiencies"):
                st["gate_admission"] = "FULL_10_PASS"
            else:
                st["gate_admission"] = "VALIDITY_PASS_POWER_DEFICIENT"
                st["power_deficiencies"] = hist_status["power_deficiencies"]
        else:
            st["gate_admission"] = "OPEN_FORWARD_MEASUREMENT"
            st["historical_validity_pass"] = False
        if st.get("status") == "BLOCKED_UNIVERSAL_GATES":'''

content = content.replace(old_admission, new_admission)

# Fix 4: Update the quarantine section
old_quarantine = '''        st.update({
            "status": "QUARANTINED_UNCERTIFIED",
            "promotion_authority": False,
            "gate_admission": "BLOCKED",
            "gate_reason": "missing exact original universal ten-gate pass",
            "last_attempt_at": attempt_at,
        })'''

new_quarantine = '''        st.update({
            "status": "QUARANTINED_UNCERTIFIED",
            "promotion_authority": False,
            "gate_admission": "BLOCKED_NO_VALIDITY_PASS",
            "gate_reason": "missing validity pass in historical certificate",
            "last_attempt_at": attempt_at,
        })'''

content = content.replace(old_quarantine, new_quarantine)

# Fix 5: Update shadow_admission.json policy description
old_policy = '''"policy": "mt5-original-universal-10-v2-calibrated-inputs",'''
new_policy = '''"policy": "mt5-open-shadow-v1-validity-gate",'''
content = content.replace(old_policy, new_policy)

# Write the fixed file
with open('/home/quant/quant-platform/desks/mt5/research/shadow_forward.py', 'w') as f:
    f.write(content)

print("shadow_forward.py updated successfully")