"""Debug: Check if callbacks are registered correctly"""
import sys
sys.path.insert(0, '.')

# Import the app
from src.gui.app import app

print("="*60)
print("Registered Callbacks:")
print("="*60)

for callback_id, callback in app.callback_map.items():
    if 'refresh' in str(callback_id).lower() or 'pred-refresh' in str(callback_id).lower():
        print(f"\n✓ Callback ID: {callback_id}")
        print(f"  Inputs: {callback['inputs']}")
        print(f"  Outputs: {callback['output']}")
        print(f"  States: {callback.get('state', [])}")

print("\n" + "="*60)
print("If you see 'pred-refresh-btn' callback above, it's registered!")
print("="*60)
