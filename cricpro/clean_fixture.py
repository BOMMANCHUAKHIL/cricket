import json

# Load the original dump
with open('datadump.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Remove all contenttypes.contenttype entries
cleaned_data = [entry for entry in data if entry['model'] != 'contenttypes.contenttype']

# Save the cleaned data to a new file
with open('cleaned_datadump.json', 'w', encoding='utf-8') as f:
    json.dump(cleaned_data, f, indent=2)

print("✅ Cleaned fixture saved as cleaned_datadump.json")
