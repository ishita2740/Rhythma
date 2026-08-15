import glob
import os

keys_str = """
  ,"insightsEducationalLibrary": "Educational Library",
  "insightsNoContent": "No content available.",
  "insightsSource": "Source",
  "insightsEducationLoadError": "Failed to load educational content."
"""

files = glob.glob(r"c:\Users\pragn\.gemini\antigravity\scratch\Rhythma\rhythma_flutter\lib\l10n\app_*.arb")

for path in files:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
        if "insightsEducationalLibrary" in content:
            print(f"Already patched {path}")
            continue

        # Find the last closing brace
        last_brace_idx = content.rfind('}')
        if last_brace_idx != -1:
            new_content = content[:last_brace_idx] + keys_str + content[last_brace_idx:]
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched {path}")
        else:
            print(f"No closing brace found in {path}")
    except Exception as e:
        print(f"Error {path}: {e}")
