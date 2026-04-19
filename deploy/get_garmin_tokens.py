"""
Run this on your local machine to generate Garmin auth tokens.
It will print a JSON blob you can paste into the app's Auth Settings page.

Install deps first:
    pip install garth garminconnect

Then run:
    python get_garmin_tokens.py
"""
import json, getpass, os, tempfile

try:
    import garth
except ImportError:
    print("Run: pip install garth")
    raise

token_dir = os.path.join(tempfile.gettempdir(), 'garth_export')
os.makedirs(token_dir, exist_ok=True)

email = input("Garmin email: ")
password = getpass.getpass("Garmin password: ")

mfa = input("MFA code (press Enter to skip): ").strip()
if mfa:
    garth.login(email, password, prompt_mfa=lambda: mfa)
else:
    garth.login(email, password)

garth.save(token_dir)

files = {}
for fname in os.listdir(token_dir):
    fpath = os.path.join(token_dir, fname)
    with open(fpath) as f:
        try:
            files[fname] = json.load(f)
        except json.JSONDecodeError:
            files[fname] = f.read()

print("\n=== PASTE THIS INTO THE APP ===\n")
print(json.dumps(files, indent=2))
print("\n================================\n")
