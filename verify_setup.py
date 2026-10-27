# ============================================================
# AeroRoute -- Environment Verification Script
# File : verify_setup.py
# Run  : python verify_setup.py
# Purpose: Confirm Python packages + MongoDB are working
# ============================================================
import sys
import importlib

print("\n" + "="*55)
print("  AeroRoute -- Environment Verification")
print("="*55)

# 1. Python version check
print(f"\n[1] Python version  : {sys.version}")
if sys.version_info < (3, 10):
    print("    [WARNING] Python 3.10+ recommended")
else:
    print("    [OK]")

# 2. Package import checks
PACKAGES = [
    ("pandas",          "pandas"),
    ("numpy",           "numpy"),
    ("pymongo",         "pymongo"),
    ("sklearn",         "scikit-learn"),
    ("networkx",        "networkx"),
    ("streamlit",       "streamlit"),
    ("plotly",          "plotly"),
    ("folium",          "folium"),
    ("dotenv",          "python-dotenv"),
    ("tqdm",            "tqdm"),
    ("openpyxl",        "openpyxl"),
]

print(f"\n[2] Package checks:")
all_ok = True
for mod, display in PACKAGES:
    try:
        m = importlib.import_module(mod)
        ver = getattr(m, "__version__", "unknown")
        print(f"    [OK]  {display:<20} {ver}")
    except ImportError:
        print(f"    [MISSING] {display} -- run: pip install {display}")
        all_ok = False

# 3. MongoDB connection check
print(f"\n[3] MongoDB connection:")
try:
    import pymongo
    from dotenv import load_dotenv
    import os
    load_dotenv()
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
    info = client.server_info()
    print(f"    [OK]  MongoDB version : {info.get('version', 'unknown')}")
    print(f"    [OK]  URI             : {uri}")
    client.close()
except Exception as e:
    print(f"    [FAIL] Cannot connect to MongoDB: {e}")
    print("    --> Is MongoDB 4.4 service running?")
    print("    --> Run: net start MongoDB")
    all_ok = False

# 4. .env file check
print(f"\n[4] .env file:")
if os.path.exists(".env"):
    print("    [OK]  .env file found")
else:
    print("    [WARN] .env not found -- copy .env.example to .env")

print("\n" + "="*55)
if all_ok:
    print("  ALL CHECKS PASSED. Ready for Phase 3.")
else:
    print("  SOME CHECKS FAILED. Fix issues above before Phase 3.")
print("="*55 + "\n")
